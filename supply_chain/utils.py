from .models import PurchaseOrder, GoodsReceiptItem
from .forms import GoodsReceiptItemForm
from django.forms import modelformset_factory
from django.db.models import Sum, F, IntegerField
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404


def weight_average_cost_calc(instance):

    inventory = instance.inventory

    inventory_qty, inventory_wac = inventory.quantity, inventory.weighted_average_cost
    inventory_value = inventory_qty * inventory_wac
    recieve_value = instance.received_quantity * instance.unit_cost_at_receipt

    new_inventory_quantity = inventory_qty + instance.received_qunatity
    new_inventory_value = inventory_value + recieve_value
    new_wac = (
        new_inventory_value / new_inventory_quantity
        if new_inventory_value or new_inventory_quantity != 0
        else 0
    )

    return inventory, new_wac, new_inventory_quantity


def get_formset_data(purchase_order):
    if not purchase_order:
        EmptyFormset = modelformset_factory(
            GoodsReceiptItem, form=GoodsReceiptItemForm, extra=0
        )
        return (
            EmptyFormset(queryset=GoodsReceiptItem.objects.none(), prefix="items"),
            [],
        )

    po_items = (
        purchase_order.po_items.annotate(
            total_received_qty=Coalesce(
                Sum("receipt_items__received_quantity"),
                0,
                output_field=IntegerField(),
            )
        )
        .filter(ordered_quantity__gt=F("total_received_qty"))
        .select_related("product")
    )

    ReceiptItemFormset = modelformset_factory(
        GoodsReceiptItem,
        form=GoodsReceiptItemForm,
        can_delete=True,
        extra=len(po_items),
    )
    initial_formset_data = [
        {"purchase_order_item": item, "product": item.product} for item in po_items
    ]

    formset = ReceiptItemFormset(
        queryset=GoodsReceiptItem.objects.none(),
        initial=initial_formset_data,
        prefix="items",
    )
    return formset, po_items


def get_initial_purchase_order(request):
    purchase_order = None
    initial_data = {}

    purchase_order_pk = request.GET.get("purchase_order")
    if purchase_order_pk:
        purchase_order = get_object_or_404(PurchaseOrder, pk=purchase_order_pk)
        initial_data["purchase_order"] = purchase_order

    return purchase_order, initial_data
