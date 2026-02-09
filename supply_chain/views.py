from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django_htmx.http import replace_url, HttpResponseClientRedirect
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
from django.forms import modelformset_factory
from django.db.models import Sum, F, IntegerField, Q, DecimalField, Value
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from render_block import render_block_to_string
from django.template.loader import render_to_string
from . import services
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from . import utils
from core.utils import apply_sorting


def suppliers(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    suppliers_list = Supplier.objects.all()

    if search_query:
        suppliers_list = suppliers_list.filter(
            Q(full_name__icontains=search_query)
            | Q(company_name__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    allowed_sort_fields = [
        "company_name",
        "full_name",
        "phone",
        "email",
        "status",
    ]
    sort_field = request.GET.get("sort", "company_name")
    direction = request.GET.get("direction", "asc")

    suppliers_list = apply_sorting(suppliers_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(suppliers_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "suppliers": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            supplier_list = render_block_to_string(
                "supply_chain/suppliers/supplier_list.html",
                "body",
                context,
            )
            return HttpResponse(supplier_list)
        else:
            supplier_list = render_block_to_string(
                "supply_chain/suppliers/supplier_list.html", "content", context
            )
            return HttpResponse(supplier_list)

    return render(request, "supply_chain/suppliers/supplier_list.html", context)





def manage_supplier(request, pk=None):
    instance = get_object_or_404(Supplier, pk=pk) if pk else None

    if request.method == "POST":
        form = SupplierForm(request.POST, instance=instance)
        if form.is_valid():
            new_instance = form.save()
            back_url = request.GET.get("next") or new_instance.get_list_url()
            return redirect(back_url)

        else:
            form = SupplierForm(instance=instance)

    form = SupplierForm(instance=instance)
    form_acion_url = (
        reverse("edit_supplier", kwargs={"pk": instance.pk})
        if instance
        else reverse("add_supplier")
    )
    context = {
        "form": form,
        "instance": instance,
        "form_acion_url": form_acion_url,
    }

    if request.htmx:
        html = render_block_to_string(
            "supply_chain/suppliers/form.html", "content", context
        )
        return HttpResponse(html)
    return render(request, "supply_chain/suppliers/form.html", context)


def delete_supplier(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == "DELETE":
        supplier.delete()
        suppliers = Supplier.objects.all()
        context = {"suppliers": suppliers}

        supplier_list = render_block_to_string(
            "supply_chain/suppliers/supplier_list.html", "content", context
        )

        success_toast = render_to_string(
            "partials/success_toast.html",
            {"message": f"{supplier.name.title()} successfully deleted."},
        )

        full_response = supplier_list + success_toast
        response = HttpResponse(full_response)
        return replace_url(response, reverse("suppliers"))


def purchases(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    purchases_list = PurchaseOrder.objects.select_related("supplier")

    if search_query:
        purchases_list = purchases_list.filter(
            Q(po_number__icontains=search_query)
            | Q(supplier__full_name__icontains=search_query)
        )

    allowed_sort_fields = [
        "po_number",
        "supplier__company_name",
        "order_date",
        "total_amount_val",
        "status",
        "delivery_status",
        "payment_status",
    ]
    sort_field = request.GET.get("sort", "-updated_at")
    if sort_field == 'total_amount':
        sort_field = 'total_amount_val'
    direction = request.GET.get("direction", "asc")

    purchases_list = apply_sorting(purchases_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(purchases_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "purchases": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            primary_html = render_block_to_string(
                "supply_chain/po/purchases.html", "body", context
            )
            return HttpResponse(primary_html)
        else:
            html = render_block_to_string(
                "supply_chain/po/purchases.html", "content", context
            )
            return HttpResponse(html)

    return render(request, "supply_chain/po/purchases.html", context)


def po_detail(request, pk):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    purchase = get_object_or_404(PurchaseOrder, pk=pk)

    search_query = request.GET.get("q", "")

    # Annotate total_amount for sorting
    purchase_list = PurchaseOrder.objects.select_related("supplier").annotate(
        total_amount_val=Coalesce(
            Sum(F("po_items__ordered_quantity") * F("po_items__unit_price_at_order"), output_field=DecimalField()),
            Value(0, output_field=DecimalField())
        )
    ).order_by("-order_date")

    if search_query:
        purchase_list = purchase_list.filter(
            Q(po_number__icontains=search_query)
            | Q(supplier__company_name__icontains=search_query)
            | Q(supplier__full_name__icontains=search_query)
        )

    paginator = Paginator(purchase_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "purchase": purchase,
        "purchase_list": page_obj,
        "search_query": search_query,
    }

    if request.htmx:
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "supply_chain/po/purchase_detail.html",
                "main_content",
                context,
            )
            return HttpResponse(html)

        elif request.htmx.target == "main_body":
            html = render_block_to_string(
                "supply_chain/po/purchase_detail.html", "content", context
            )
            return HttpResponse(html)

        else:
            html = render_block_to_string(
                "supply_chain/po/purchase_detail.html", "side_bar_list", context
            )
            return HttpResponse(html)

    else:
        return render(request, "supply_chain/po/purchase_detail.html", context)


def manage_purchases(request, pk=None):
    instance = get_object_or_404(PurchaseOrder, pk=pk) if pk else None
    queryset = instance.po_items.all() if instance else PurchaseOrderItem.objects.none()

    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, instance=instance)
        formset = PurchaseOrderItemFormSet(
            request.POST, queryset=queryset, prefix="items"
        )

        if form.is_valid() and formset.is_valid():
            services.process_po(form, formset, request.user)
            return redirect("purchases")
    else:
        form = PurchaseOrderForm(instance=instance)
        formset = PurchaseOrderItemFormSet(queryset=queryset, prefix="items")

    form_action_url = (
        reverse("edit_po", kwargs={"pk": instance.pk})
        if instance
        else reverse("add_po")
    )

    context = {
        "po_form": form,
        "item_formset": formset,
        "form_action_url": form_action_url,
    }

    if request.htmx:
        return HttpResponse(
            render_block_to_string("supply_chain/po/form.html", "content", context)
        )

    return render(request, "supply_chain/po/form.html", context)


def manage_po_item(request):
    try:
        current_index = int(request.GET.get("index", "0"))
    except ValueError:
        current_index = 0

    formset = PurchaseOrderItemFormSet(prefix="items")
    empty_form = formset.empty_form
    empty_form.prefix = f"items-{current_index}"

    context = {"form": empty_form}
    return render(request, "supply_chain/po/partials/po_item_form_row.html", context)


def delete_po(request, pk):
    purchase = get_object_or_404(PurchaseOrder, pk=pk)

    if request.method == "DELETE":
        purchase.delete()
        purchases = PurchaseOrder.objects.select_related("supplier")
        context = {"purchases": purchases}

        purchase_list = render_block_to_string(
            "supply_chain/po/purchases.html", "content", context
        )

        success_toast = render_to_string(
            "partials/success_toast.html",
            {"message": f"{purchase.po_number} successfully deleted."},
        )

        response = HttpResponse(purchase_list + success_toast)
        return replace_url(response, reverse("purchases"))


def payments(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    payments_list = Payment.objects.select_related("purchase_order__supplier")

    if search_query:
        payments_list = payments_list.filter(
            Q(trxn_ref__icontains=search_query)
            | Q(purchase_order__po_number__icontains=search_query)
            | Q(purchase_order__supplier__full_name__icontains=search_query)
        )

    paginator = Paginator(payments_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"payments": page_obj, "search_query": search_query}

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            primary_html = render_block_to_string(
                "supply_chain/payment_made/payment_list.html",
                "body",
                context,
            )
            return HttpResponse(primary_html)
        else:
            html = render_block_to_string(
                "supply_chain/payment_made/payment_list.html", "content", context
            )
            return HttpResponse(html)

    return render(request, "supply_chain/payment_made/payment_list.html", context)


def payments_detail(request, pk):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    payment = get_object_or_404(Payment, pk=pk)
    payment_list = Payment.objects.select_related("purchase_order").order_by("-payment_date")

    search_query = request.GET.get("q", "")
    if search_query:
        payment_list = payment_list.filter(
            Q(trxn_ref__icontains=search_query)
            | Q(purchase_order__po_number__icontains=search_query)
        )

    allowed_sort_fields = [
        "trxn_ref",
        "payment_date",
        "payment_method",
        "amount_paid",
        "status",
        "purchase_order__po_number",
        "purchase_order__supplier__company_name",
    ]
    sort_field = request.GET.get("sort", "-payment_date")
    direction = request.GET.get("direction", "asc")

    payment_list = apply_sorting(payment_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(payment_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "payment": payment,
        "payment_list": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "supply_chain/payment_made/payment_detail.html",
                "main_content",
                context,
            )
            return HttpResponse(html)

        elif request.htmx.target == "main_body":
            html = render_block_to_string(
                "supply_chain/payment_made/payment_detail.html", "content", context
            )
            return HttpResponse(html)

        else:
            html = render_block_to_string(
                "supply_chain/payment_made/payment_detail.html",
                "side_bar_list",
                context,
            )
            return HttpResponse(html)

    else:
        return render(request, "supply_chain/payment_made/payment_detail.html", context)


def manage_payments(request):
    purchase_order, initial_data = utils.get_initial_purchase_order(request)

    if request.method == "POST":
        paymentform = PaymentForm(request.POST)
        print(request.POST)
        print(paymentform.is_valid())
        if paymentform.is_valid():
            with transaction.atomic():
                paymentform = paymentform.save(commit=False)
                paymentform.created_by = request.user
                paymentform.updated_by = request.user
                paymentform.save()

                return (
                    redirect(purchase_order.get_absolute_url)
                    if purchase_order
                    else redirect("payments")
                )
    else:
        paymentform = PaymentForm(initial=initial_data)

    context = {
        "paymentform": paymentform,
        "form_action_url": request.get_full_path(),
    }

    if request.htmx:
        html = render_block_to_string(
            "supply_chain/payment_made/form.html", "content", context
        )
        return HttpResponse(html)

    return render(request, "supply_chain/payment_made/form.html", context)


def payments_void(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == "POST":
        if payment.can_void:
            payment.mark_as_void()
            message = f"Payment {payment.trxn_ref} has been voided"
        else:
            message = f"{payment.trxn_ref} can not be voided"

        context = {"payment": payment}

        void_partial = render_block_to_string(
            "supply_chain/payment_made/payment_detail.html",
            "void",
            context,
        )
        success_toast = render_to_string(
            "partials/toast.html",
            {"message": message},
        )

        response = void_partial + success_toast
        return HttpResponse(response)


def good_receipts(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    receipts_list = GoodsReceipt.objects.select_related("purchase_order")

    if search_query:
        receipts_list = receipts_list.filter(
            Q(gr_number__icontains=search_query)
            | Q(purchase_order__po_number__icontains=search_query)
        )

    allowed_sort_fields = [
        "gr_number",
        "delivery_date",
        "status",
        "purchase_order__po_number",
        "purchase_order__supplier__company_name",
    ]
    sort_field = request.GET.get("sort", "-updated_at")
    direction = request.GET.get("direction", "asc")

    receipts_list = apply_sorting(receipts_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(receipts_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "receipts": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            primary_html = render_block_to_string(
                "supply_chain/goods_receipts/receipts.html",
                "body",
                context,
            )
            return HttpResponse(primary_html)
        else:
            html = render_block_to_string(
                "supply_chain/goods_receipts/receipts.html", "content", context
            )
            return HttpResponse(html)

    return render(request, "supply_chain/goods_receipts/receipts.html", context)


def receipt_detail(request, pk):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    receipt = get_object_or_404(
        GoodsReceipt.objects.prefetch_related("receipt_items__product__inventory"),
        pk=pk,
    )
    receipt_list = GoodsReceipt.objects.select_related("purchase_order__supplier").order_by("-delivery_date")

    search_query = request.GET.get("q", "")
    if search_query:
        receipt_list = receipt_list.filter(
            Q(receipt_number__icontains=search_query)
            | Q(purchase_order__po_number__icontains=search_query)
        )

    paginator = Paginator(receipt_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "receipt": receipt,
        "can_void": services.can_void_receipt(receipt),
        "receipt_list": page_obj,
        "search_query": search_query,
    }

    if request.htmx:
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "supply_chain/goods_receipts/receipt_detail.html",
                "main_content",
                context,
            )
            return HttpResponse(html)

        elif request.htmx.target == "main_body":
            html = render_block_to_string(
                "supply_chain/goods_receipts/receipt_detail.html", "content", context
            )
            return HttpResponse(html)

        else:
            html = render_block_to_string(
                "supply_chain/goods_receipts/receipt_detail.html",
                "side_bar_list",
                context,
            )
            return HttpResponse(html)

    else:
        return render(
            request, "supply_chain/goods_receipts/receipt_detail.html", context
        )


def manage_receipts(request):
    zipped_data = None
    formset = None
    purchase_order, initial_data = utils.get_initial_purchase_order(request)

    if request.method == "POST":
        form = GoodsReceiptForm(request.POST)
        formset = GoodsReceiptItemFormset(request.POST, prefix="items")

        if form.is_valid() and formset.is_valid():
            services.process_receipt(form, formset, request.user)
            return (
                redirect(purchase_order.get_absolute_url)
                if purchase_order
                else redirect("receipts")
            )
        else:
            po_item_ids = [
                form["purchase_order_item"].value()
                for form in formset.forms
                if form["purchase_order_item"].value()
            ]

            if po_item_ids:
                items_dict = (
                    PurchaseOrderItem.objects.filter(pk__in=po_item_ids)
                    .select_related("product")
                    .in_bulk()
                )
                po_items = [
                    items_dict.get(uuid.UUID(pk))
                    for pk in po_item_ids
                    if items_dict.get(uuid.UUID(pk))
                ]
            else:
                po_items = []

            zipped_data = zip(formset.forms, po_items)

    else:
        form = GoodsReceiptForm(initial=initial_data)
        formset, po_items = utils.get_formset_data(purchase_order)
        zipped_data = zip(formset.forms, po_items)

    context = {
        "form": form,
        "formset": formset,
        "zipped_data": zipped_data,
        "form_action_url": reverse("add_receipt"),
        "receipt_item_url": reverse("receipt_item_form"),
    }

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "supply_chain/goods_receipts/form.html",
                "content",
                context,
                request=request,
            )
        )

    return render(request, "supply_chain/goods_receipts/form.html", context)


def manage_receipt_item(request):
    purchase_order = None

    if request.GET.get("purchase_order"):
        purchase_order_pk = request.GET.get("purchase_order")
        purchase_order = get_object_or_404(PurchaseOrder, pk=purchase_order_pk)

    formset, po_items = utils.get_formset_data(purchase_order)
    zipped_data = zip(formset.forms, po_items)

    context = {
        "formset": formset,
        "zipped_data": zipped_data,
    }

    return render(
        request, "supply_chain/goods_receipts/partials/receipt_item_form.html", context
    )


@require_POST
def void_receipt(request, pk):
    receipt = get_object_or_404(
        GoodsReceipt.objects.prefetch_related("receipt_items__product__inventory"),
        pk=pk,
    )

    if services.can_void_receipt(receipt):
        services.void_and_correct(pk, request.user)
        message = f"Receipt {receipt.gr_number} has been voided"
    else:
        message = f"{receipt.gr_number} can not be voided"

    void_block = render_block_to_string(
        "supply_chain/goods_receipts/receipt_detail.html",
        "void",
        {"receipt": receipt},
    )
    toast = render_to_string(
        "partials/toast.html",
        {"message": message},
    )

    return HttpResponse(void_block + toast)
