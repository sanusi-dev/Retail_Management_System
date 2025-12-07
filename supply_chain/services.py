from django.db import transaction
from .models import *


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


def can_void_receipt(receipt):
    if receipt.status == GoodsReceipt.Status.VOIDED:
        return False
    for item in receipt.receipt_items.all():
        current_qty = item.product.inventory.quantity
        if current_qty < item.received_quantity:
            return False
    return True


def void_and_correct(receipt_id, user):
    with transaction.atomic():
        receipt = (
            GoodsReceipt.objects.select_for_update().select_related().get(pk=receipt_id)
        )
        if not can_void_receipt(receipt):
            raise ValueError("This is inventory can not be voided")
        for item in receipt.receipt_items.all():
            item.create_reversal(user)

    receipt.status = GoodsReceipt.Status.VOIDED
    receipt.save(update_fields=["status"])
