from django.dispatch import Signal
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete
from django.dispatch import receiver
from .models import GoodsReceiptItem, Payment
from inventory.models import Product, Inventory

# from customer.models import Sale
from django.db import transaction
from django.db.models import F
from utils.utils import create_inventory_transaction


@receiver([post_delete, post_save], sender=GoodsReceiptItem)
def update_po_status(sender, instance, created=None, **kwargs):
    po = instance.goods_receipt.purchase_order
    po.update_po_delivery_status()
    po.update_po_status()


@receiver([post_delete, post_save], sender=GoodsReceiptItem)
def update_po_item_status(sender, instance, created=None, **kwargs):
    po_item = instance.purchase_order_item
    po_item.update_po_item_status()


@receiver(post_save, sender=GoodsReceiptItem)
def update_inventory(sender, instance, created, **kwargs):
    if not created:
        return

    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(product=instance.product)

        qty = instance.received_quantity
        cost = instance.unit_cost_at_receipt

        new_qty = inventory.quantity + qty
        total_value = (inventory.quantity * inventory.weighted_average_cost) + (
            qty * cost
        )
        wac = total_value / new_qty if new_qty > 0 else 0

        inventory.quantity = new_qty
        inventory.weighted_average_cost = wac
        inventory.save(update_fields=["quantity", "weighted_average_cost"])


@receiver(post_save, sender=GoodsReceiptItem)
def create_inventory_trxn(sender, instance, created, **kwargs):
    if not created:
        return

    from inventory.models import InventoryTransaction

    if not instance.reverses:
        create_inventory_transaction(
            inventory=instance.product.inventory,
            source=instance,
            transaction_type=InventoryTransaction.TransactionType.RECEIPT,
            quantity_change=instance.received_quantity,
            cost_impact=instance.received_quantity * instance.unit_cost_at_receipt,
        )


@receiver([post_delete, post_save], sender=Payment)
def update_po_payment_status(sender, instance, created=None, **kwargs):
    po = instance.purchase_order
    po.update_po_payment_status()
    po.update_po_status()
