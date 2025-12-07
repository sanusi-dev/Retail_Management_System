from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal

from inventory import services
from inventory.models import Inventory, InventoryTransaction, TransformationItem
from .models import (
    Customer,
    DepositAccount,
    Transaction,
    PurchaseAgreement,
    CfaFulfillment,
    CfaAgreement,
    BoxedSale,
    CoupledSale,
    Sale,
)


# ACCOUNT & AGREEMENT LIFECYCLE
# Handles creation of accounts and status updates for agreements.


@receiver(post_save, sender=Customer)
def create_deposit_account(sender, instance, created, **kwargs):
    """Automatically create a deposit account when a customer is created."""
    if created:
        DepositAccount.objects.create(
            customer=instance,
            created_by=instance.created_by,
            updated_by=instance.updated_by,
        )


def update_agreement_status_logic(line_item):
    """Helper to update line item and parent agreement status."""
    line_item.update_status()
    line_item.purchase_agreement.update_status()


@receiver(post_save, sender=BoxedSale)
@receiver(post_delete, sender=BoxedSale)
def update_status_on_boxed_sale_change(sender, instance, **kwargs):
    if instance.agreement_line_item:
        update_agreement_status_logic(instance.agreement_line_item)


@receiver(post_save, sender=CoupledSale)
@receiver(post_delete, sender=CoupledSale)
def update_status_on_coupled_sale_change(sender, instance, **kwargs):
    if instance.agreement_line_item:
        update_agreement_status_logic(instance.agreement_line_item)


@receiver(post_save, sender=CfaFulfillment)
@receiver(post_delete, sender=CfaFulfillment)
def update_cfa_statuses_after_fulfillment(sender, instance, **kwargs):
    instance.cfa_agreement.update_status()


@receiver(pre_delete, sender=PurchaseAgreement)
def prevent_deletion_of_fulfilled_agreements(sender, instance, **kwargs):
    if instance.agreement_sales.exists():
        raise ValidationError(
            "Cannot delete a Purchase Agreement that already has linked Sales. "
            "Void the sales first."
        )


# INVENTORY MANAGEMENT (DEDUCTIONS)
# Handles removing items from stock when Sales are created.


@receiver(post_save, sender=BoxedSale)
def update_inventory_on_sale_save(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            inventory = Inventory.objects.select_for_update().get(
                product=instance.product
            )
            inventory.quantity -= instance.quantity
            inventory.save(update_fields=["quantity"])

            services.create_inventory_transaction(
                inventory=inventory,
                source=instance,
                transaction_type=InventoryTransaction.TransactionType.SALE,
                quantity_change=-instance.quantity,
                cost_impact=inventory.weighted_average_cost * instance.quantity,
            )


@receiver(post_save, sender=CoupledSale)
def mark_item_sold(sender, instance, created, **kwargs):
    if created:
        with transaction.atomic():
            item = TransformationItem.objects.select_for_update().get(
                pk=instance.transformation_item.pk
            )
            if item.status == TransformationItem.Status.SOLD:
                raise ValidationError("This Item is already sold!")

            item.status = TransformationItem.Status.SOLD
            item.save(update_fields=["status"])


# FINANCIAL TRANSACTIONS (WITHDRAWALS)
# Handles deducting money from Deposit Accounts when Sales/Fulfillments occur.


@receiver(post_save, sender=BoxedSale)
def create_withdrawal_for_boxed_sale(sender, instance, created, **kwargs):
    if created and instance.sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
        total_amount = instance.price * instance.quantity

        ct = ContentType.objects.get_for_model(instance)

        if not Transaction.objects.filter(
            source_object_id=instance.pk, source_content_type=ct
        ).exists():
            Transaction.objects.create(
                account=instance.sale.customer.deposit_account,
                transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                amount=total_amount,
                source=instance,
                note=f"Auto-withdrawal for Boxed Sale {instance.boxed_sale_number}",
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )


@receiver(post_save, sender=CoupledSale)
def create_withdrawal_for_coupled_sale(sender, instance, created, **kwargs):
    if created and instance.sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
        total_amount = instance.price
        ct = ContentType.objects.get_for_model(instance)

        if not Transaction.objects.filter(
            source_object_id=instance.pk, source_content_type=ct
        ).exists():
            Transaction.objects.create(
                account=instance.sale.customer.deposit_account,
                transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                amount=total_amount,
                source=instance,
                note=f"Auto-withdrawal for Coupled Sale {instance.coupled_sale_number}",
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )


@receiver(post_save, sender=CfaFulfillment)
def create_withdrawal_after_cfa_fulfillment(sender, instance, created, **kwargs):
    if created:
        naira_amount = instance.cfa_amount_disbursed_to_naira
        ct = ContentType.objects.get_for_model(instance)

        if not Transaction.objects.filter(
            source_object_id=instance.pk, source_content_type=ct
        ).exists():
            Transaction.objects.create(
                account=instance.cfa_agreement.account,
                transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                amount=naira_amount,
                source=instance,
                note=f"Naira settlement for CFA Fulfillment {instance.fulfillment_number}",
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )


@receiver(post_save, sender=CfaFulfillment)
def create_refund_after_cfa_fulfillment_void(sender, instance, created, **kwargs):
    if not created:
        naira_amount = instance.cfa_amount_disbursed_to_naira
        print(naira_amount)
        ct = ContentType.objects.get_for_model(instance)

        if not Transaction.objects.filter(
            source_object_id=instance.pk,
            source_content_type=ct,
            transaction_type=Transaction.TransactionType.DEPOSIT_REFUND,
        ).exists():
            Transaction.objects.create(
                account=instance.cfa_agreement.account,
                transaction_type=Transaction.TransactionType.DEPOSIT_REFUND,
                amount=abs(naira_amount),
                source=instance,
                note=f"Naira Refund for voided fulfillment {instance.fulfillment_number}",
                created_by=instance.created_by,
                updated_by=instance.updated_by,
            )


# SALE VOIDING & DELETION (REVERSALS)
# Handles returning Stock and Money when things are Voided or Deleted.


@receiver(pre_save, sender=Sale)
def track_status_change(sender, instance, **kwargs):
    """Checks if the status is changing to VOIDED."""
    if not instance._state.adding:
        try:
            old_instance = Sale.objects.get(pk=instance.pk)
            instance._status_changed_to_void = (
                old_instance.status != Sale.Status.VOIDED
                and instance.status == Sale.Status.VOIDED
            )
        except Sale.DoesNotExist:
            instance._status_changed_to_void = False
    else:
        instance._status_changed_to_void = False


@receiver(post_save, sender=Sale)
def process_sale_voiding(sender, instance, created, **kwargs):
    """
    If Sale is voided:
    1. Return Inventory
    2. Reset Coupled Items
    3. Refund Money (if applicable)
    """
    if created:
        return

    if not getattr(instance, "_status_changed_to_void", False):
        return

    with transaction.atomic():
        # Return Boxed Inventory
        boxed_sales = instance.boxed_sales.all()
        boxed_total_value = Decimal("0.00")

        if boxed_sales.exists():
            for boxed_sale in boxed_sales:
                inventory = Inventory.objects.select_for_update().get(
                    product=boxed_sale.product
                )
                inventory.quantity += boxed_sale.quantity
                inventory.save(update_fields=["quantity"])

                services.create_inventory_transaction(
                    inventory=inventory,
                    source=boxed_sale,
                    transaction_type=InventoryTransaction.TransactionType.SALE_REVERSAL,
                    quantity_change=boxed_sale.quantity,
                    cost_impact=inventory.weighted_average_cost * boxed_sale.quantity,
                )
                boxed_total_value += boxed_sale.price * boxed_sale.quantity

        # Reset Coupled Items
        coupled_sales = instance.coupled_sales.all()
        coupled_total_value = Decimal("0.00")

        if coupled_sales.exists():
            for coupled_sale in coupled_sales:
                TransformationItem.objects.select_for_update().filter(
                    pk=coupled_sale.transformation_item.pk
                ).update(status=TransformationItem.Status.AVAILABLE)

                coupled_total_value += coupled_sale.price

        # Refund Money
        if instance.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            total_refund_amount = boxed_total_value + coupled_total_value
            if total_refund_amount > 0:
                Transaction.objects.create(
                    account=instance.customer.deposit_account,
                    transaction_type=Transaction.TransactionType.DEPOSIT,
                    amount=total_refund_amount,
                    source=instance,
                    note=f"Refund for Voided Sale {instance.sale_number}",
                    created_by=instance.updated_by,
                    updated_by=instance.updated_by,
                )


@receiver(post_delete, sender=BoxedSale)
def return_inventory_on_sale_deletion(sender, instance, **kwargs):
    """Return stock if a BoxedSale is manually deleted via Admin."""
    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(product=instance.product)
        inventory.quantity += instance.quantity
        inventory.save(update_fields=["quantity"])

        services.create_inventory_transaction(
            inventory=inventory,
            source=instance,
            transaction_type=InventoryTransaction.TransactionType.SALE_REVERSAL,
            quantity_change=instance.quantity,
            cost_impact=inventory.weighted_average_cost * instance.quantity,
        )


@receiver(post_delete, sender=CoupledSale)
def mark_item_available(sender, instance, **kwargs):
    """Make item available again if CoupledSale is manually deleted."""
    with transaction.atomic():
        TransformationItem.objects.select_for_update().filter(
            pk=instance.transformation_item.pk
        ).update(status=TransformationItem.Status.AVAILABLE)
