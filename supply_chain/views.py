from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
from django.forms import modelformset_factory
from django.db.models import Sum, F, IntegerField
from django.db.models.functions import Coalesce


@login_required(login_url="/admin/login/")
def suppliers(request):
    suppliers = Supplier.objects.all()
    context = {"suppliers": suppliers}
    return render(request, "supply_chain/suppliers/supplier_list.html", context)


@login_required(login_url="/admin/login/")
def manage_supplier(request, pk=None):
    supplier = get_object_or_404(Supplier, pk=pk) if pk else None

    if request.method == "POST":
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            supplier = form.save()
            if not pk and request.GET.get("next"):
                return redirect(request.GET.get("next"))
            return redirect("suppliers")
    else:
        form = SupplierForm(instance=supplier)

    context = {
        "form": form,
        "is_editing": pk is not None,
    }
    return render(request, "supply_chain/suppliers/form.html", context)


def supplier_detail(request, pk):
    pass


@login_required(login_url="/admin/login/")
def delete_supplier(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == "POST":
        supplier.delete()
        return redirect("suppliers")


@login_required(login_url="/admin/login/")
def purchases(request):
    purchases = PurchaseOrder.objects.select_related("supplier")
    context = {"purchases": purchases}
    return render(request, "supply_chain/po/purchases.html", context)


def manage_purchases(request, pk=None):
    po_instance = get_object_or_404(PurchaseOrder, pk=pk) if pk else None
    if po_instance:
        queryset = po_instance.po_items.all()
    else:
        queryset = PurchaseOrderItem.objects.none()

    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, instance=po_instance)
        formset = PurchaseOrderItemFormSet(
            request.POST, queryset=queryset, prefix="items"
        )

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                po = form.save(commit=False)
                if not po.created_by_id:
                    po.created_by = request.user
                po.updated_by = request.user
                po.save()

                items = formset.save(commit=False)
                for item in items:
                    item.purchase_order = po
                    if not item.created_by_id:
                        item.created_by = request.user
                    item.updated_by = request.user
                    item.save()

                formset.save()
                return redirect("purchases")

    else:

        form = PurchaseOrderForm(instance=po_instance)
        formset = PurchaseOrderItemFormSet(queryset=queryset, prefix="items")
    context = {
        "po_form": form,
        "item_formset": formset,
    }
    return render(request, "supply_chain/po/form.html", context)


def po_detail(request, pk):
    pass


def delete_po(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == "POST":
        po.delete()
        return redirect("purchases")


def htmx_add_po_item(request):
    # Get the index for the new form from the request parameters
    try:
        current_index = int(request.GET.get("index", "0"))
    except (ValueError, TypeError):
        current_index = 0

    formset = PurchaseOrderItemFormSet(prefix="items")
    empty_form = formset.empty_form
    empty_form.prefix = f"items-{current_index}"

    context = {"form": empty_form}
    return render(request, "supply_chain/po/partials/po_item_form_row.html", context)


def payments(request):
    payments = Payment.objects.select_related("purchase_order__supplier")
    context = {"payments": payments}
    return render(request, "supply_chain/payment_made/payment_list.html", context)


def payments_detail(request):
    pass


def payments_create(request):
    if request.method == "POST":
        paymentform = PaymentForm(request.POST)
        if paymentform.is_valid():
            with transaction.atomic():
                paymentform = paymentform.save(commit=False)
                paymentform.created_by = request.user
                paymentform.updated_by = request.user
                paymentform.save()

                return redirect("payments")
    else:
        paymentform = PaymentForm()

    context = {"paymentform": paymentform}
    return render(request, "supply_chain/payment_made/form.html", context)


def payments_void(request):
    pass


@login_required(login_url="/admin/login/")
def good_receipts(request):
    receipts = GoodsReceipt.objects.select_related("purchase_order")
    context = {"receipts": receipts}
    return render(request, "supply_chain/goods_receipts/receipts.html", context)


def manage_goods_receipts(request, pk=None):
    instance = get_object_or_404(GoodsReceipt, pk=pk) if pk else None

    formset = None
    zipped_data = None

    if request.method == "POST":
        form = GoodsReceiptForm(request.POST, instance=instance)

        if pk:
            queryset = instance.receipt_items.all()
            formset = GoodsReceiptItemFormset(
                request.POST, queryset=queryset, prefix="items"
            )
        else:
            formset = GoodsReceiptItemFormset(request.POST, prefix="items")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                receipt = form.save(commit=False)
                if not receipt.created_by_id:
                    receipt.created_by = request.user
                receipt.updated_by = request.user
                receipt.received_by = request.user
                receipt.save()

                items = formset.save(commit=False)
                for item in items:
                    item.goods_receipt = receipt
                    if not item.created_by_id:
                        item.created_by = request.user
                    item.updated_by = request.user
                    item.save()
                formset.save()
            return redirect("receipts")
        else:
            if pk:
                queryset = instance.receipt_items.all()
                po_items = [item.purchase_order_item for item in queryset]

            po_id = request.POST.get("purchase_order")
            if po_id:
                po_items = PurchaseOrderItem.objects.filter(
                    purchase_order_id=po_id
                ).select_related("product")
            zipped_data = zip(formset.forms, po_items)

    else:
        form = GoodsReceiptForm(instance=instance)
        if pk and instance:
            queryset = instance.receipt_items.all()
            formset = GoodsReceiptItemFormset(queryset=queryset, prefix="items")
            po_items = [item.purchase_order_item for item in queryset]
            zipped_data = zip(formset.forms, po_items)

    context = {
        "form": form,
        "formset": formset,
        "zipped_data": zipped_data,
        "has_existing_instance": instance is not None,
    }
    return render(request, "supply_chain/goods_receipts/form.html", context)


def receipt_detail(request, pk):
    pass


def delete_receipt(request, pk):
    receipt = get_object_or_404(GoodsReceipt, pk=pk)
    if request.method == "POST":
        receipt.delete()
        return redirect("receipts")


def htmx_get_receipt_item_form(request, pk=None):
    instance = get_object_or_404(GoodsReceipt, pk=pk) if pk else None
    po_id = request.GET.get("purchase_order")
    po_items = []

    if pk and instance:
        queryset = instance.receipt_items.all()
        formset = GoodsReceiptItemFormset(queryset=queryset, prefix="items")
        po_items = [item.purchase_order_item for item in queryset]

    elif not pk and po_id:
        po_items = (
            PurchaseOrderItem.objects.annotate(
                total_received_qty=Coalesce(
                    Sum("receipt_items__received_quantity"),
                    0,
                    output_field=IntegerField(),
                )
            )
            .filter(
                purchase_order_id=po_id, ordered_quantity__gt=F("total_received_qty")
            )
            .select_related("product")
        )

        initial_data = [
            {"purchase_order_item": item, "product": item.product} for item in po_items
        ]

        ReceiptItemFormset_dynamic = modelformset_factory(
            GoodsReceiptItem,
            form=GoodsReceiptItemForm,
            can_delete=True,
            extra=len(po_items),
        )

        formset = ReceiptItemFormset_dynamic(
            queryset=GoodsReceiptItem.objects.none(),
            initial=initial_data,
            prefix="items",
        )

    else:
        return HttpResponse(status=204)

    zipped_data = zip(formset.forms, po_items)
    context = {
        "formset": formset,
        "zipped_data": zipped_data,
        "has_existing_instance": instance is not None,
    }
    return render(
        request, "supply_chain/goods_receipts/partials/receipt_item_form.html", context
    )
