import logging
from django.db import transaction
from .models import *
from core.utils import audit

logger = logging.getLogger(__name__)


class BusinessRuleViolation(Exception):
    pass


def _update_po_status(po):
    """Update PO delivery status, payment status, and overall status."""
    po.update_po_delivery_status()
    po.update_po_payment_status()
    po.update_po_status()


def process_po(form, formset, user):
    with transaction.atomic():
        po = form.save(commit=False)
        if not po.created_by_id:
            po.created_by = user
        po.updated_by = user
        po.save()

        items = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()

        for item in items:
            item.purchase_order = po
            if not item.created_by_id:
                item.created_by = user
            item.updated_by = user
            item.save()


def process_receipt(form, formset, user):
    """
    Process a goods receipt: save items, recalculate WAC, update inventory,
    create inventory transactions, update PO statuses.
    Replaces update_inventory, create_inventory_trxn, update_po_status,
    update_po_item_status signals.
    """
    from inventory.models import Inventory, InventoryTransaction, InventoryCostLayer
    from inventory.utils import create_inventory_transaction

    with transaction.atomic():
        receipt = form.save(commit=False)
        receipt.created_by = user
        receipt.updated_by = user
        receipt.save()

        items = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()

        delivery_cost = receipt.delivery_cost
        total_received_qty = sum(item.received_quantity for item in items)
        allocated_delivery_cost_per_unit = (
            delivery_cost / total_received_qty
            if delivery_cost != 0 and total_received_qty > 0
            else 0
        )

        for item in items:
            item.goods_receipt = receipt
            item.allocated_delivery_cost_per_unit = allocated_delivery_cost_per_unit
            item.unit_cost_at_receipt = (
                item.purchase_order_item.unit_price_at_order
                + allocated_delivery_cost_per_unit
            )
            item.created_by = user
            item.updated_by = user
            item.save()

            # WAC recalculation and inventory update (replaces update_inventory signal)
            inventory = Inventory.objects.select_for_update().get(product=item.product)
            qty = item.received_quantity
            cost = item.unit_cost_at_receipt

            new_qty = inventory.quantity + qty
            total_value = (inventory.quantity * inventory.weighted_average_cost) + (
                qty * cost
            )
            wac = total_value / new_qty if new_qty > 0 else 0

            inventory.quantity = new_qty
            inventory.weighted_average_cost = wac
            inventory.save(update_fields=["quantity", "weighted_average_cost", "updated_at"])

            # Create FIFO cost layer for this receipt batch
            InventoryCostLayer.objects.create(
                product=item.product,
                quantity=qty,
                remaining_quantity=qty,
                unit_cost=cost,
                goods_receipt_item=item,
            )

            # Create inventory transaction (replaces create_inventory_trxn signal)
            if not item.reverses:
                create_inventory_transaction(
                    inventory=item.product.inventory,
                    source=item,
                    transaction_type=InventoryTransaction.TransactionType.RECEIPT,
                    quantity_change=item.received_quantity,
                    cost_impact=item.received_quantity * item.unit_cost_at_receipt,
                )

            # Update PO item status (replaces update_po_item_status signal)
            po_item = item.purchase_order_item
            po_item.update_po_item_status()

        # Update PO statuses (replaces update_po_status signal)
        po = receipt.purchase_order
        _update_po_status(po)


def can_void_receipt(receipt):
    if receipt.status == GoodsReceipt.Status.VOIDED:
        return False
    for item in receipt.receipt_items.all():
        current_qty = item.product.inventory.quantity
        if current_qty < item.received_quantity:
            return False
    return True 


def void_and_correct(receipt_id, user, request=None):
    """
    Void a goods receipt: create reversals, restore inventory, update PO statuses.
    Replaces reverse_inventory_on_receipt_void, update_po_status,
    update_po_item_status signals.
    """
    from inventory.models import Inventory, InventoryTransaction, InventoryCostLayer
    from inventory.utils import create_inventory_transaction

    with transaction.atomic():
        receipt = (
            GoodsReceipt.objects.select_for_update().select_related().get(pk=receipt_id)
        )
        if not can_void_receipt(receipt):
            raise BusinessRuleViolation("This receipt cannot be voided — insufficient stock.")

        for item in receipt.receipt_items.all():
            # Create reversal item (this already creates the InventoryTransaction via model method)
            item.create_reversal(user)

            # Handle FIFO cost layer — mark as voided (one layer per receipt item)
            from django.utils import timezone
            cost_layer = InventoryCostLayer.objects.filter(
                goods_receipt_item=item,
            ).select_for_update().first()

            if cost_layer:
                if cost_layer.remaining_quantity < item.received_quantity:
                    sold = item.received_quantity - cost_layer.remaining_quantity
                    raise BusinessRuleViolation(
                        f"Cannot void receipt: {sold} units from GR item {item.pk} "
                        f"have already been sold and cannot be reversed."
                    )
                cost_layer.is_voided = True
                cost_layer.remaining_quantity = 0
                cost_layer.voided_at = timezone.now()
                cost_layer.save(update_fields=["is_voided", "remaining_quantity", "voided_at"])

            # Restore inventory and recalculate WAC (replaces reverse_inventory signal)
            inventory = Inventory.objects.select_for_update().get(product=item.product)
            qty = item.received_quantity
            cost = item.unit_cost_at_receipt

            new_qty = inventory.quantity - qty
            if new_qty > 0:
                total_value = (inventory.quantity * inventory.weighted_average_cost) - (
                    qty * cost
                )
                wac = total_value / new_qty
            else:
                wac = 0

            inventory.quantity = new_qty
            inventory.weighted_average_cost = wac
            inventory.save(update_fields=["quantity", "weighted_average_cost", "updated_at"])

            # Update PO item status
            po_item = item.purchase_order_item
            po_item.update_po_item_status()

        receipt.status = GoodsReceipt.Status.VOIDED
        receipt.save(update_fields=["status"])

        # Update PO statuses
        po = receipt.purchase_order
        _update_po_status(po)

        audit(user, 'void_receipt', receipt, detail={
            'gr_number': receipt.gr_number,
            'po_number': receipt.purchase_order.po_number,
        }, request=request)


def record_supplier_payment(po, amount, method, user, trxn_ref="", remark=""):
    """
    Record a supplier payment and update PO payment status.
    Replaces update_po_payment_status signal.
    """
    with transaction.atomic():
        payment = Payment(
            purchase_order=po,
            amount_paid=amount,
            payment_method=method,
            remark=remark,
            created_by=user,
            updated_by=user,
        )
        if trxn_ref:
            payment.trxn_ref = trxn_ref
        payment.save()

        # Update PO statuses (replaces update_po_payment_status signal)
        _update_po_status(po)
    return payment


def void_supplier_payment(payment_id, user, request=None):
    """
    Void a supplier payment and update PO payment status.
    Replaces update_po_payment_status signal.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)

        if not payment.can_void:
            raise BusinessRuleViolation("This payment cannot be voided.")

        payment.status = Payment.Status.VOIDED
        payment.updated_by = user
        payment.save(update_fields=['status', 'updated_by'])

        # Update PO statuses (replaces update_po_payment_status signal)
        _update_po_status(payment.purchase_order)

        audit(user, 'void_supplier_payment', payment, detail={
            'amount': str(payment.amount_paid),
            'payment_method': payment.payment_method,
            'po_number': payment.purchase_order.po_number,
            'trxn_ref': payment.trxn_ref,
        }, request=request)

    return payment
