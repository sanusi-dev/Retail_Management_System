from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *


@login_required(login_url="/admin/login/")
def suppliers(request):
    suppliers = Supplier.objects.prefetch_related("purchase_orders__po_items")
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
    purchases = PurchaseOrder.objects.select_related()
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
    """
    This view is called by HTMX to add a new item form to the formset.
    """
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
