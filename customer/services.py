import logging
from decimal import Decimal
from django.db import DatabaseError, IntegrityError, OperationalError
from django.db import transaction as db_transaction
from django.db.models import F
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from core.utils import audit

logger = logging.getLogger(__name__)


class BusinessRuleViolation(Exception):
    """Raised when a service call violates a business rule."""
    pass


class InsufficientFundsError(BusinessRuleViolation):
    pass


class InsufficientStockError(BusinessRuleViolation):
    pass


def _refresh_balances(account):
    """
    Private helper. Recalculates and saves all three cached balance fields.
    Call at the end of any service that changes transactions, agreements, or sales.
    """
    from customer.models import DepositAccount

    try:
        with db_transaction.atomic():
            account_locked = DepositAccount.objects.select_for_update().get(
                pk=account.pk
            )
            account_locked.cached_total_balance = account_locked._calculate_total_balance()
            account_locked.cached_allocated_balance = account_locked._calculate_allocated_balance()
            account_locked.cached_available_balance = (
                account_locked.cached_total_balance - account_locked.cached_allocated_balance
            )
            from django.utils import timezone
            account_locked.balances_last_updated = timezone.now()
            account_locked.save(update_fields=[
                'cached_total_balance',
                'cached_allocated_balance',
                'cached_available_balance',
                'balances_last_updated',
            ])
    except (DatabaseError, IntegrityError, OperationalError):
        logger.error(
            "Balance cache refresh failed for account %s", account.pk,
            exc_info=True
        )
        raise


def _update_agreement_status(line_item):
    """Helper to update line item and parent agreement status."""
    line_item.update_status()
    line_item.purchase_agreement.update_status()


def record_deposit(account, amount, note, user, request=None, created_at=None):
    """Create a deposit transaction and refresh balances."""
    from customer.models import Transaction

    with db_transaction.atomic():
        txn = Transaction.objects.create(
            account=account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=amount,
            note=note,
            created_by=user,
            updated_by=user,
        )
        if created_at is not None:
            txn.created_at = created_at
            txn.save(update_fields=["created_at"])
        _refresh_balances(account)
    return txn


def record_withdrawal(account, amount, note, user, request=None, created_at=None):
    """Create a withdrawal transaction and refresh balances."""
    from customer.models import Transaction

    with db_transaction.atomic():
        txn = Transaction(
            account=account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=amount,
            note=note,
            created_by=user,
            updated_by=user,
        )
        txn.full_clean()
        txn.save()
        if created_at is not None:
            txn.created_at = created_at
            txn.save(update_fields=["created_at"])
        _refresh_balances(account)

        audit(user, 'create_withdrawal', txn, detail={
            'amount': str(amount),
            'account_id': str(account.pk),
        }, request=request)

    return txn


def void_deposit(transaction_id, void_reason, user, request=None):
    """Void a deposit or withdrawal transaction if allowed."""
    from customer.models import Transaction

    with db_transaction.atomic():
        txn = Transaction.objects.select_for_update().get(pk=transaction_id)

        if txn.status == Transaction.Status.VOIDED:
            raise BusinessRuleViolation("Transaction is already voided.")

        if txn.transaction_type not in [
            Transaction.TransactionType.DEPOSIT,
            Transaction.TransactionType.WITHDRAWAL,
        ]:
            raise BusinessRuleViolation("Only manual transactions can be voided this way.")

        txn.status = Transaction.Status.VOIDED
        txn.updated_by = user
        txn.save(update_fields=['status', 'updated_by'])

        _refresh_balances(txn.account)

        audit_action = (
            'void_deposit'
            if txn.transaction_type == Transaction.TransactionType.DEPOSIT
            else 'void_withdrawal'
        )
        audit(user, audit_action, txn, detail={
            'void_reason': void_reason,
            'amount': str(txn.amount),
            'account_id': str(txn.account.pk),
        }, request=request)

    return txn


def create_purchase_agreement(account, line_items_data, user, request=None):
    """
    Create a purchase agreement with line items.
    line_items_data: list of dicts with 'product', 'quantity_ordered', 'price_per_unit'
    """
    from customer.models import PurchaseAgreement, PurchaseAgreementLineItem

    with db_transaction.atomic():
        agreement = PurchaseAgreement(
            account=account,
            created_by=user,
            updated_by=user,
        )
        agreement.save()

        for item_data in line_items_data:
            line_item = PurchaseAgreementLineItem(
                purchase_agreement=agreement,
                product=item_data['product'],
                quantity_ordered=item_data['quantity_ordered'],
                price_per_unit=item_data['price_per_unit'],
                created_by=user,
                updated_by=user,
            )
            line_item.save()

        _refresh_balances(account)
    return agreement


def cancel_agreement(agreement_id, user, request=None):
    """Cancel a purchase agreement and refresh balances."""
    from customer.models import PurchaseAgreement, PurchaseAgreementLineItem

    with db_transaction.atomic():
        agreement = PurchaseAgreement.objects.select_for_update().get(pk=agreement_id)

        if not agreement.can_cancel:
            raise BusinessRuleViolation("This agreement cannot be cancelled.")

        agreement.status = PurchaseAgreement.Status.CANCELLED
        agreement.save(update_fields=["status"])

        for item in agreement.agreement_line_items.all():
            item.status = PurchaseAgreementLineItem.Status.CANCELLED
            item.save(update_fields=["status"])

        _refresh_balances(agreement.account)

        audit(user, 'cancel_agreement', agreement, detail={
            'agreement_number': agreement.purchase_agreement_number,
            'account_id': str(agreement.account.pk),
        }, request=request)

    return agreement


def create_cfa_agreement(account, amount_naira, exchange_rate, user, request=None):
    """Create a CFA agreement."""
    from customer.models import CfaAgreement

    with db_transaction.atomic():
        cfa = CfaAgreement(
            account=account,
            amount_allocated=amount_naira,
            exchange_rate=exchange_rate,
            created_by=user,
            updated_by=user,
        )
        cfa.save()
        _refresh_balances(account)
    return cfa


def record_cfa_fulfillment(agreement_id, cfa_amount, notes, user, request=None, created_at=None):
    """Record a CFA fulfillment and create withdrawal transaction."""
    from customer.models import CfaFulfillment, Transaction

    with db_transaction.atomic():
        agreement = CfaAgreement = __import__('customer.models', fromlist=['CfaAgreement']).CfaAgreement
        agreement = agreement.objects.select_for_update().get(pk=agreement_id)

        fulfillment = CfaFulfillment(
            cfa_agreement=agreement,
            cfa_amount_disbursed=cfa_amount,
            notes=notes,
            created_by=user,
            updated_by=user,
        )
        fulfillment.save()

        # Create withdrawal transaction (replaces create_withdrawal_after_cfa_fulfillment signal)
        naira_amount = fulfillment.cfa_amount_disbursed_to_naira
        ct = ContentType.objects.get_for_model(fulfillment)

        if not Transaction.objects.filter(
            source_object_id=fulfillment.pk, source_content_type=ct
        ).exists():
            txn = Transaction.objects.create(
                account=agreement.account,
                transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                amount=naira_amount,
                source=fulfillment,
                note=f"Naira settlement for CFA Fulfillment {fulfillment.fulfillment_number}",
                created_by=user,
                updated_by=user,
            )
            if created_at is not None:
                txn.created_at = created_at
                txn.save(update_fields=["created_at"])

        # Update CFA agreement status (replaces update_cfa_statuses_after_fulfillment signal)
        agreement.update_status()
        _refresh_balances(agreement.account)
    return fulfillment


def void_cfa_fulfillment(fulfillment_id, void_reason, user, request=None):
    """Void a CFA fulfillment and reverse its withdrawal transaction."""
    from customer.models import CfaFulfillment, Transaction

    with db_transaction.atomic():
        fulfillment = CfaFulfillment.objects.select_for_update().get(pk=fulfillment_id)

        if fulfillment.status == CfaFulfillment.Status.VOIDED:
            raise BusinessRuleViolation("Fulfillment is already voided.")

        fulfillment.status = CfaFulfillment.Status.VOIDED
        fulfillment.updated_by = user
        fulfillment.save(update_fields=['status', 'updated_by'])

        # Void the original FULFILLMENT_WITHDRAWAL transaction so it no longer
        # counts against the balance (balance calc filters by status=ACTIVE).
        ct = ContentType.objects.get_for_model(fulfillment)
        withdrawal_txn = Transaction.objects.filter(
            source_object_id=fulfillment.pk,
            source_content_type=ct,
            transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
            status=Transaction.Status.ACTIVE,
        ).first()

        if withdrawal_txn:
            withdrawal_txn.status = Transaction.Status.VOIDED
            withdrawal_txn.updated_by = user
            withdrawal_txn.save(update_fields=['status', 'updated_by'])

        # Update CFA agreement status
        fulfillment.cfa_agreement.update_status()
        _refresh_balances(fulfillment.cfa_agreement.account)

        audit(user, 'void_cfa_fulfillment', fulfillment, detail={
            'fulfillment_number': fulfillment.fulfillment_number,
            'cfa_amount': str(fulfillment.cfa_amount_disbursed),
            'cfa_agreement_id': str(fulfillment.cfa_agreement.pk),
            'void_reason': void_reason,
        }, request=request)

    return fulfillment


def cancel_cfa_agreement(agreement_id, user, request=None):
    """Cancel a CFA agreement and refresh balances."""
    from customer.models import CfaAgreement

    with db_transaction.atomic():
        agreement = CfaAgreement.objects.select_for_update().get(pk=agreement_id)

        if not agreement.can_cancel:
            raise BusinessRuleViolation("This CFA agreement cannot be cancelled.")

        agreement.status = CfaAgreement.Status.CANCELLED
        agreement.save(update_fields=["status"])

        _refresh_balances(agreement.account)

        audit(user, 'cancel_cfa_agreement', agreement, detail={
            'cfa_agreement_number': agreement.cfa_agreement_number,
            'amount_allocated': str(agreement.amount_allocated),
            'account_id': str(agreement.account.pk),
        }, request=request)

    return agreement


def create_sale(sale, boxed_items, coupled_items, user, request=None):
    """
    Complete a sale: save items, decrement inventory, create withdrawals, update statuses.
    sale: already-created Sale instance (from form.save(commit=False))
    boxed_items: list of BoxedSale instances (from formset.save(commit=False))
    coupled_items: list of CoupledSale instances (from formset.save(commit=False))
    """
    from customer.models import (
        Sale, BoxedSale, CoupledSale, Transaction, PurchaseAgreementLineItem,
        BoxedSaleLayerConsumption,
    )
    from inventory.models import Inventory, InventoryTransaction, TransformationItem
    from inventory.services import _deplete_fifo_layers
    from inventory.utils import create_inventory_transaction

    with db_transaction.atomic():
        sale.save()

        # Process boxed items
        for item in boxed_items:
            item.sale = sale
            if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT and item.agreement_line_item:
                if item.price is None:
                    item.price = item.agreement_line_item.price_per_unit
            item.save()

            # Decrement inventory (replaces update_inventory_on_sale_save signal)
            inventory = Inventory.objects.select_for_update().get(product=item.product)
            inventory.quantity -= item.quantity
            inventory.save(update_fields=["quantity"])

            # FIFO depletion and cost capture
            fifo_cost, consumptions = _deplete_fifo_layers(item.product, item.quantity)
            item.cost_basis = fifo_cost
            item.save(update_fields=["cost_basis"])

            # Record each layer consumed for granular reversal (Fix 1)
            for entry in consumptions:
                BoxedSaleLayerConsumption.objects.create(
                    boxed_sale=item,
                    cost_layer=entry["layer"],
                    quantity_consumed=entry["quantity"],
                    unit_cost=entry["unit_cost"],
                )

            create_inventory_transaction(
                inventory=inventory,
                source=item,
                transaction_type=InventoryTransaction.TransactionType.SALE,
                quantity_change=-item.quantity,
                cost_impact=fifo_cost,
            )

            # Update agreement status (replaces update_status_on_boxed_sale_change signal)
            if item.agreement_line_item:
                _update_agreement_status(item.agreement_line_item)

            # Create withdrawal for deposit sales (replaces create_withdrawal_for_boxed_sale signal)
            if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
                total_amount = item.price * item.quantity
                ct = ContentType.objects.get_for_model(item)
                if not Transaction.objects.filter(
                    source_object_id=item.pk, source_content_type=ct
                ).exists():
                    Transaction.objects.create(
                        account=sale.customer.deposit_account,
                        transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                        amount=total_amount,
                        source=item,
                        note=f"Auto-withdrawal for Boxed Sale {item.boxed_sale_number}",
                        created_by=user,
                        updated_by=user,
                    )

        # Process coupled items
        for item in coupled_items:
            item.sale = sale
            if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT and item.agreement_line_item:
                if item.price is None:
                    item.price = item.agreement_line_item.price_per_unit
            item.save()

            # Mark transformation item as sold (replaces mark_item_sold signal)
            ti = TransformationItem.objects.select_for_update().get(
                pk=item.transformation_item.pk
            )
            if ti.status == TransformationItem.Status.SOLD:
                raise BusinessRuleViolation("This Item is already sold!")
            ti.status = TransformationItem.Status.SOLD
            ti.save(update_fields=["status"])

            # Update agreement status (replaces update_status_on_coupled_sale_change signal)
            if item.agreement_line_item:
                _update_agreement_status(item.agreement_line_item)

            # Create withdrawal for deposit sales (replaces create_withdrawal_for_coupled_sale signal)
            if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
                total_amount = item.price
                ct = ContentType.objects.get_for_model(item)
                if not Transaction.objects.filter(
                    source_object_id=item.pk, source_content_type=ct
                ).exists():
                    Transaction.objects.create(
                        account=sale.customer.deposit_account,
                        transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                        amount=total_amount,
                        source=item,
                        note=f"Auto-withdrawal for Coupled Sale {item.coupled_sale_number}",
                        created_by=user,
                        updated_by=user,
                    )

        # Refresh balances if deposit sale
        if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            _refresh_balances(sale.customer.deposit_account)

    return sale


def void_sale(sale_id, void_reason, user, request=None):
    """
    Void a sale and reverse all its side effects.
    Replaces process_sale_voiding + track_status_change signals.
    """
    from customer.models import (
        Sale, BoxedSale, CoupledSale, Transaction, PurchaseAgreementLineItem,
    )
    from inventory.models import Inventory, InventoryTransaction, TransformationItem
    from inventory.utils import create_inventory_transaction

    with db_transaction.atomic():
        sale = Sale.objects.select_for_update().get(pk=sale_id)

        if sale.status == Sale.Status.VOIDED:
            raise BusinessRuleViolation("Sale is already voided.")

        boxed_total_value = Decimal("0.00")
        coupled_total_value = Decimal("0.00")

        # Return Boxed Inventory
        for boxed_sale in sale.boxed_sales.all():
            inventory = Inventory.objects.select_for_update().get(
                product=boxed_sale.product
            )
            inventory.quantity += boxed_sale.quantity
            inventory.save(update_fields=["quantity"])

            # Restore original FIFO layers via consumption records (Fix 1)
            consumptions = boxed_sale.layer_consumptions.all()
            if consumptions.exists():
                reversal_cost = Decimal("0.00")
                for c in consumptions:
                    c.cost_layer.remaining_quantity += c.quantity_consumed
                    c.cost_layer.save(update_fields=["remaining_quantity"])
                    reversal_cost += Decimal(str(c.quantity_consumed)) * c.unit_cost
            elif boxed_sale.cost_basis is not None:
                # Legacy: sale recorded cost_basis but not layer_consumptions
                from inventory.services import _restore_fifo_layer
                reversal_cost = boxed_sale.cost_basis
                unit_cost = boxed_sale.cost_basis / boxed_sale.quantity
                _restore_fifo_layer(boxed_sale.product, boxed_sale.quantity, unit_cost)
            else:
                reversal_cost = inventory.weighted_average_cost * boxed_sale.quantity

            create_inventory_transaction(
                inventory=inventory,
                source=boxed_sale,
                transaction_type=InventoryTransaction.TransactionType.SALE_REVERSAL,
                quantity_change=boxed_sale.quantity,
                cost_impact=reversal_cost,
            )
            boxed_total_value += boxed_sale.price * boxed_sale.quantity

        # Reset Coupled Items
        for coupled_sale in sale.coupled_sales.all():
            TransformationItem.objects.select_for_update().filter(
                pk=coupled_sale.transformation_item.pk
            ).update(status=TransformationItem.Status.AVAILABLE)
            coupled_total_value += coupled_sale.price

        # Refund Money for deposit sales
        if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            total_refund_amount = boxed_total_value + coupled_total_value
            if total_refund_amount > 0:
                Transaction.objects.create(
                    account=sale.customer.deposit_account,
                    transaction_type=Transaction.TransactionType.DEPOSIT,
                    amount=total_refund_amount,
                    source=sale,
                    note=f"Refund for Voided Sale {sale.sale_number}",
                    created_by=user,
                    updated_by=user,
                )

        # Mark sale voided (use queryset update to bypass full_clean limit_choices_to)
        Sale.objects.filter(pk=sale.pk).update(
            status=Sale.Status.VOIDED,
            void_reason=void_reason,
            updated_by=user,
        )
        sale.status = Sale.Status.VOIDED

        # Update agreement statuses (must happen AFTER sale is marked voided,
        # because total_quantity_fulfilled filters by sale status=ACTIVE)
        for boxed_sale in sale.boxed_sales.all():
            if boxed_sale.agreement_line_item:
                _update_agreement_status(boxed_sale.agreement_line_item)
        for coupled_sale in sale.coupled_sales.all():
            if coupled_sale.agreement_line_item:
                _update_agreement_status(coupled_sale.agreement_line_item)

        # Refresh balances
        if sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            _refresh_balances(sale.customer.deposit_account)

        audit(user, 'void_sale', sale, detail={
            'void_reason': void_reason,
            'total': str(sale.sales_total),
            'payment_method': sale.payment_method,
        }, request=request)

    return sale


def amend_line_item(line_item_id, new_quantity, new_price_per_unit, reason, user, request=None):
    """Create a new version of an existing agreement line item."""
    from customer.models import PurchaseAgreement, PurchaseAgreementLineItem

    with db_transaction.atomic():
        old_item = PurchaseAgreementLineItem.objects.select_for_update().select_related(
            "purchase_agreement__account"
        ).get(pk=line_item_id)

        if not old_item.is_current_version:
            raise BusinessRuleViolation("Only the current version of a line item can be amended.")

        if old_item.status in (
            PurchaseAgreementLineItem.Status.VOIDED,
            PurchaseAgreementLineItem.Status.CANCELLED,
        ):
            raise BusinessRuleViolation("Cannot amend a voided or cancelled line item.")

        fulfilled = old_item.quantity_fulfilled_accross_all_versions
        if new_quantity < fulfilled:
            raise BusinessRuleViolation(
                f"Cannot set quantity below {fulfilled} — {fulfilled} units have already been fulfilled."
            )

        account = old_item.purchase_agreement.account
        old_allocated = (old_item.quantity_ordered - fulfilled) * old_item.price_per_unit
        new_allocated = (new_quantity - fulfilled) * new_price_per_unit
        allocation_increase = new_allocated - old_allocated

        if allocation_increase > 0:
            available = account.available_balance
            if allocation_increase > available:
                raise BusinessRuleViolation(
                    f"Insufficient available balance. "
                    f"Amendment requires ₦{allocation_increase:,.2f} more, "
                    f"but only ₦{available:,.2f} is available."
                )

        new_version = old_item.version + 1

        new_item = PurchaseAgreementLineItem(
            purchase_agreement=old_item.purchase_agreement,
            line_number=old_item.line_number,
            product=old_item.product,
            quantity_ordered=new_quantity,
            price_per_unit=new_price_per_unit,
            version=new_version,
            is_current_version=True,
            superseded_by=None,
            created_by=user,
            updated_by=user,
        )
        new_item.save()

        old_item.is_current_version = False
        old_item.superseded_by = new_item
        old_item.save(update_fields=["is_current_version", "superseded_by"])

        _refresh_balances(account)

        audit(user, 'amend_line_item', new_item, detail={
            'line_number': old_item.line_number,
            'old_version': old_item.version,
            'new_version': new_item.version,
            'old_quantity': old_item.quantity_ordered,
            'new_quantity': new_quantity,
            'old_price': str(old_item.price_per_unit),
            'new_price': str(new_price_per_unit),
            'allocation_increase': str(allocation_increase),
            'reason': reason,
            'agreement_number': old_item.purchase_agreement.purchase_agreement_number,
        }, request=request)

    return new_item
