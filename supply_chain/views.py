from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django_htmx.http import replace_url, HttpResponseClientRedirect
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import *
from .forms import *
from django.forms import modelformset_factory
from django.db.models import Sum, F, IntegerField, Q, DecimalField, Value, Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from . import services
from django.contrib import messages
from django.urls import reverse
from . import utils
from core.utils import apply_sorting


def suppliers(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    suppliers_list = Supplier.objects.annotate(
        open_po_count=Count("purchase_orders", filter=~Q(purchase_orders__status="closed")),
        total_ordered_ytd=Coalesce(
            Subquery(
                PurchaseOrder.objects.filter(
                    supplier=OuterRef("pk"),
                )
                .annotate(total=Sum(F("po_items__ordered_quantity") * F("po_items__unit_price_at_order")))
                .values("total")[:1],
                output_field=DecimalField(),
            ),
            Value(0, output_field=DecimalField()),
        ),
    )

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
        "open_po_count",
        "total_ordered_ytd",
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
        if "q" in request.GET or "sort" in request.GET or "page" in request.GET:
            return render(request, "supply_chain/suppliers/supplier_list.html#supplier-table-partial", context)
        return render(request, "supply_chain/suppliers/supplier_list.html#supplier-list-partial", context)

    return render(request, "supply_chain/suppliers/supplier_list.html", context)


def modal_manage_supplier(request, pk=None):
    instance = get_object_or_404(Supplier, pk=pk) if pk else None

    if request.method == "POST":
        form = SupplierForm(request.POST, instance=instance)
        if form.is_valid():
            supplier = form.save(commit=False)
            if not instance:
                supplier.created_by = request.user
            supplier.updated_by = request.user
            supplier.save()
            messages.success(
                request,
                f"Supplier {supplier.company_name} {'updated' if instance else 'created'}.",
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "supplierChanged"
            return response
    else:
        form = SupplierForm(instance=instance)

    return render(
        request,
        "supply_chain/suppliers/modals/manage_supplier_modal.html",
        {
            "form": form,
            "instance": instance,
        },
    )


def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    active_tab = request.GET.get("tab", "pos")

    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)

    purchase_orders = supplier.purchase_orders.annotate(
        total_amount_val=Coalesce(
            Sum(F("po_items__ordered_quantity") * F("po_items__unit_price_at_order"), output_field=DecimalField()),
            Value(0, output_field=DecimalField())
        )
    ).prefetch_related("po_items__product").order_by("-order_date")

    paginator = Paginator(purchase_orders, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    payments = Payment.objects.filter(
        purchase_order__supplier=supplier
    ).select_related("purchase_order").order_by("-payment_date")[:50]

    total_ordered_ytd = purchase_orders.aggregate(
        total=Coalesce(Sum("total_amount_val"), Value(0, output_field=DecimalField()))
    )["total"] or Decimal("0.00")

    open_po_count = supplier.purchase_orders.filter(~Q(status="closed")).count()

    undelivered_value = sum(po.po_total_undelivered_value for po in supplier.purchase_orders.all())

    context = {
        "supplier": supplier,
        "active_tab": active_tab,
        "purchase_orders": page_obj,
        "payments": payments,
        "total_ordered_ytd": total_ordered_ytd,
        "open_po_count": open_po_count,
        "undelivered_value": undelivered_value,
    }

    if request.htmx:
        return render(
            request,
            "supply_chain/suppliers/supplier_detail.html#supplier-detail-partial",
            context,
        )

    return render(request, "supply_chain/suppliers/supplier_detail.html", context)


def delete_supplier(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)

    if request.method == "DELETE":
        supplier.delete()
        suppliers = Supplier.objects.all()
        context = {"suppliers": suppliers}

        supplier_list = render_to_string(
            "supply_chain/suppliers/supplier_list.html#supplier-list-partial", context, request=request
        )

        success_toast = render_to_string(
            "partials/toast.html",
            {"message": f"{supplier.name.title()} successfully deleted."},
        )

        full_response = supplier_list + success_toast
        response = HttpResponse(full_response)
        return replace_url(response, reverse("suppliers"))


def purchases(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    filter_status = request.GET.get("status", "")
    filter_payment = request.GET.get("payment", "")
    filter_delivery = request.GET.get("delivery", "")
    filter_supplier = request.GET.get("supplier", "")

    purchases_list = PurchaseOrder.objects.select_related("supplier").annotate(
        total_amount_val=Coalesce(
            Sum(F("po_items__ordered_quantity") * F("po_items__unit_price_at_order"), output_field=DecimalField()),
            Value(0, output_field=DecimalField()),
        )
    ).order_by("-updated_at")

    if search_query:
        purchases_list = purchases_list.filter(
            Q(po_number__icontains=search_query)
            | Q(supplier__full_name__icontains=search_query)
        )

    if filter_status:
        purchases_list = purchases_list.filter(status=filter_status)
    if filter_payment:
        purchases_list = purchases_list.filter(payment_status=filter_payment)
    if filter_delivery:
        purchases_list = purchases_list.filter(delivery_status=filter_delivery)
    if filter_supplier:
        purchases_list = purchases_list.filter(supplier__pk=filter_supplier)

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
    if sort_field == "total_amount":
        sort_field = "total_amount_val"
    direction = request.GET.get("direction", "asc")

    purchases_list = apply_sorting(purchases_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(purchases_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    all_suppliers = Supplier.objects.filter(status="active").order_by("company_name", "full_name")

    context = {
        "purchases": page_obj,
        "search_query": search_query,
        "filter_status": filter_status,
        "filter_payment": filter_payment,
        "filter_delivery": filter_delivery,
        "filter_supplier": filter_supplier,
        "all_suppliers": all_suppliers,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if any(key in request.GET for key in ["page", "q", "status", "payment", "delivery", "supplier", "sort"]):
            return render(
                request,
                "supply_chain/po/purchases.html#po-table-partial",
                context,
            )
        return render(
            request,
            "supply_chain/po/purchases.html#po-list-partial",
            context,
        )

    return render(request, "supply_chain/po/purchases.html", context)


def po_detail(request, pk):
    purchase = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier").prefetch_related(
            "po_items__product",
            "payments",
            "goods_receipts",
        ),
        pk=pk,
    )

    context = {
        "purchase": purchase,
    }

    if request.htmx:
        return render(
            request,
            "supply_chain/po/purchase_detail.html#po-detail-partial",
            context,
        )

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
            try:
                services.process_po(form, formset, request.user)
                messages.success(
                    request,
                    f"Purchase Order {form.instance.po_number} {'updated' if instance else 'created'}.",
                )
                return redirect("purchases")
            except Exception as e:
                messages.error(request, f"Error occurred while processing Purchase Order: {str(e)}")
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
        "formset": formset,
        "form_action_url": form_action_url,
        "is_creating": instance is None,
        "po": instance,
    }

    if request.htmx:
        return render(
            request,
            "supply_chain/po/form.html#po-form-partial",
            context,
        )

    return render(request, "supply_chain/po/form.html", context)


def po_line_item_add(request):
    """
    Receives the full current form state via POST (hx-include="closest form").
    Appends one empty row by incrementing TOTAL_FORMS and seeding blank fields.
    Returns the re-rendered #formset-container partial.
    """
    post_data = request.POST.copy()
    total_forms = int(post_data.get("items-TOTAL_FORMS", 0))

    post_data[f"items-{total_forms}-product"] = ""
    post_data[f"items-{total_forms}-ordered_quantity"] = ""
    post_data[f"items-{total_forms}-unit_price_at_order"] = ""
    post_data["items-TOTAL_FORMS"] = total_forms + 1

    formset = PurchaseOrderItemFormSet(post_data, prefix="items")

    return render(
        request,
        "supply_chain/po/form.html#po-formset-partial",
        {"formset": formset},
    )


def po_line_item_remove(request, index):
    """
    Receives the full current form state via POST (hx-include="closest form")
    and the index of the row to operate on from the URL.

    Logic:
    - If the row has a pk (items-{index}-id is non-empty): the row is an
      existing DB record. Toggle its DELETE flag. If it was unmarked, mark it
      "on". If it was already "on", unmark it (undo).
    - If the row has no pk: it is a new unsaved row. Shift all rows above
      this index down by one, decrement TOTAL_FORMS, drop the row entirely.

    Returns the re-rendered #formset-container partial.
    """
    post_data = request.POST.copy()
    total_forms = int(post_data.get("items-TOTAL_FORMS", 0))
    pk_value = post_data.get(f"items-{index}-id", "").strip()

    if pk_value:
        # Existing DB record — toggle DELETE
        already_deleted = post_data.get(f"items-{index}-DELETE", "") == "on"
        if already_deleted:
            post_data.pop(f"items-{index}-DELETE", None)
        else:
            post_data[f"items-{index}-DELETE"] = "on"

        formset = PurchaseOrderItemFormSet(post_data, prefix="items")

    else:
        # New unsaved row — remove by shifting indexes
        import urllib.parse
        from django.http import QueryDict

        line_fields = ["id", "product", "ordered_quantity", "unit_price_at_order", "DELETE"]
        new_data = {}
        new_index = 0

        for i in range(total_forms):
            if i == index:
                continue
            for field in line_fields:
                old_key = f"items-{i}-{field}"
                if old_key in post_data:
                    new_data[f"items-{new_index}-{field}"] = post_data[old_key]
            new_index += 1

        new_data["items-TOTAL_FORMS"] = new_index
        new_data["items-INITIAL_FORMS"] = post_data.get("items-INITIAL_FORMS", 0)
        new_data["items-MIN_NUM_FORMS"] = post_data.get("items-MIN_NUM_FORMS", 0)
        new_data["items-MAX_NUM_FORMS"] = post_data.get("items-MAX_NUM_FORMS", 1000)

        encoded = urllib.parse.urlencode(new_data, doseq=True)
        rebuilt = QueryDict(encoded, mutable=True)

        formset = PurchaseOrderItemFormSet(rebuilt, prefix="items")

    return render(
        request,
        "supply_chain/po/form.html#po-formset-partial",
        {"formset": formset},
    )


def delete_po(request, pk):
    purchase = get_object_or_404(PurchaseOrder, pk=pk)

    if request.method == "DELETE":
        purchase.delete()
        purchases = PurchaseOrder.objects.select_related("supplier")
        context = {"purchases": purchases}

        purchase_list = render_to_string(
            "supply_chain/po/purchases.html#content", context, request=request
        )

        success_toast = render_to_string(
            "partials/toast.html",
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

    payments_list = apply_sorting(payments_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(payments_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"payments": page_obj, "search_query": search_query, "sort_field": sort_field, "direction": direction}

    if request.htmx:
        if "q" in request.GET or "sort" in request.GET or "page" in request.GET:
            return render(request, "supply_chain/payment_made/payment_list.html#payment-table-partial", context)
        return render(request, "supply_chain/payment_made/payment_list.html#payment-list-partial", context)

    return render(request, "supply_chain/payment_made/payment_list.html", context)


def modal_manage_payment(request):
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = services.record_supplier_payment(
                    po=form.cleaned_data['purchase_order'],
                    amount=form.cleaned_data['amount_paid'],
                    method=form.cleaned_data['payment_method'],
                    user=request.user,
                    remark=form.cleaned_data.get('remark', ''),
                )
                messages.success(request, f"Payment {payment.trxn_ref} recorded.")
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "poDetailChanged"
                return response
            except Exception as e:
                form.add_error(None, str(e))
    else:
        initial = {}
        purchase_order = None
        po_pk = request.GET.get("purchase_order")
        if po_pk:
            try:
                purchase_order = PurchaseOrder.objects.get(pk=po_pk)
                initial["purchase_order"] = purchase_order
            except PurchaseOrder.DoesNotExist:
                pass
        form = PaymentForm(initial=initial)

    return render(
        request,
        "supply_chain/payment_made/modals/manage_payment_modal.html",
        {"form": form},
    )


def payments_detail(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("purchase_order__supplier", "created_by"),
        pk=pk,
    )

    context = {
        "payment": payment,
    }

    if request.htmx:
        return render(
            request,
            "supply_chain/payment_made/payment_detail.html#payment-detail-partial",
            context,
        )

    return render(request, "supply_chain/payment_made/payment_detail.html", context)


def modal_void_payment(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("purchase_order__supplier"), pk=pk
    )

    if request.method == "POST":
        void_reason = request.POST.get("void_reason", "")
        try:
            services.void_supplier_payment(pk, request.user, request=request)
            messages.success(request, f"Payment {payment.trxn_ref} voided.")
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "paymentChanged"
            return response

        except services.BusinessRuleViolation as e:
            error_msg = str(e)
            return render(
                request,
                "supply_chain/payment_made/modals/void_payment_modal.html",
                {
                    "payment": payment,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "supply_chain/payment_made/modals/void_payment_modal.html",
        {
            "payment": payment,
        },
    )


def good_receipts(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    filter_status = request.GET.get("status", "")
    receipts_list = GoodsReceipt.objects.select_related("purchase_order")

    if search_query:
        receipts_list = receipts_list.filter(
            Q(gr_number__icontains=search_query)
            | Q(purchase_order__po_number__icontains=search_query)
        )

    if filter_status:
        receipts_list = receipts_list.filter(status=filter_status)

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
        "filter_status": filter_status,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if any(key in request.GET for key in ["page", "q", "status", "sort"]):
            return render(
                request,
                "supply_chain/goods_receipts/receipts.html#receipt-table-partial",
                context,
            )
        return render(
            request,
            "supply_chain/goods_receipts/receipts.html#receipt-list-partial",
            context,
        )

    return render(request, "supply_chain/goods_receipts/receipts.html", context)


def receipt_detail(request, pk):
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related(
            "purchase_order", "purchase_order__supplier"
        ).prefetch_related("receipt_items__product", "receipt_items__purchase_order_item"),
        pk=pk,
    )

    context = {
        "receipt": receipt,
        "can_void": services.can_void_receipt(receipt),
    }

    if request.htmx:
        return render(
            request,
            "supply_chain/goods_receipts/receipt_detail.html#receipt-detail-partial",
            context,
        )

    return render(request, "supply_chain/goods_receipts/receipt_detail.html", context)


def modal_void_receipt(request, pk):
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related("purchase_order"), pk=pk
    )

    if request.method == "POST":
        void_reason = request.POST.get("void_reason", "")
        try:
            services.void_and_correct(receipt.pk, request.user, request=request)
            messages.success(request, f"Receipt {receipt.gr_number} voided successfully.")
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "receiptDetailChanged"
            return response

        except services.BusinessRuleViolation as e:
            error_msg = str(e)
            return render(
                request,
                "supply_chain/goods_receipts/modals/void_receipt_modal.html",
                {
                    "receipt": receipt,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "supply_chain/goods_receipts/modals/void_receipt_modal.html",
        {
            "receipt": receipt,
        },
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

            zipped_data = list(zip(formset.forms, po_items))

    else:
        form = GoodsReceiptForm(initial=initial_data)
        formset, po_items = utils.get_formset_data(purchase_order)
        zipped_data = list(zip(formset.forms, po_items))

    context = {
        "form": form,
        "formset": formset,
        "zipped_data": zipped_data,
        "form_action_url": reverse("add_receipt"),
        "receipt_item_url": reverse("receipt_item_form"),
        "purchase_order": purchase_order,
    }

    if request.htmx:
        return render(
            request,
            "supply_chain/goods_receipts/form.html#receipt-form-partial",
            context,
        )

    return render(request, "supply_chain/goods_receipts/form.html", context)


def manage_receipt_item(request):
    purchase_order = None

    if request.GET.get("purchase_order"):
        purchase_order_pk = request.GET.get("purchase_order")
        purchase_order = get_object_or_404(PurchaseOrder, pk=purchase_order_pk)

    formset, po_items = utils.get_formset_data(purchase_order)
    zipped_data = list(zip(formset.forms, po_items))

    context = {
        "formset": formset,
        "zipped_data": zipped_data,
    }

    return render(
        request,
        "supply_chain/goods_receipts/partials/receipt_item_form.html",
        context,
    )
