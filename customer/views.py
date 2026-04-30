from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_GET
from render_block import render_block_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import HttpResponse
from django_htmx.http import HttpResponseClientRedirect
from django.db.models import Sum, F, DecimalField, Value, Q
from django.db.models.functions import Coalesce
from .models import (
    Customer,
    Transaction,
    DepositAccount,
    PurchaseAgreement,
    PurchaseAgreementLineItem,
    CfaAgreement,
    CfaFulfillment,
    Sale,
    CoupledSale,
    BoxedSale,
)
from .forms import (
    CustomerForm,
    TransactionForm,
    PurchaseAgreementForm,
    PurchaseAgreementLineItemForm,
    PurchaseAgreementLineItemFormSet,
    CfaAgreementForm,
    CfaFulfillmentForm,
    CfaFulfillmentForm,
    NormalSaleForm,
    RecordSaleForm,
    AgreementSaleForm,
    BoxedSaleFormSet,
    CoupledSaleFormSet,
)
from . import services as customer_services
from inventory.models import Product, TransformationItem
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.db import transaction
from django.db.models import Sum, Count, Q, F, Prefetch
from django.db.models.functions import Coalesce
import logging

logger = logging.getLogger(__name__)


def customers(request):
    search_query = request.GET.get("q", "")
    customer_list = Customer.objects.select_related("deposit_account").order_by(
        "-deposit_account__cached_total_balance"
    )

    if search_query:
        customer_list = customer_list.filter(
            Q(full_name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(customer_id__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "deposit_account__cached_total_balance")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = [
        "full_name",
        "deposit_account__cached_total_balance",
        "phone",
        "customer_id",
    ]

    if direction == "desc":
        order_by_field = f"-{sort_field}"
    else:
        order_by_field = sort_field

    if sort_field in allowed_sort_fields:
        customer_list = customer_list.order_by(order_by_field)

    # Pagination
    PAGE_SIZE = 100
    paginator = Paginator(customer_list, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "customers": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            customer_list = render_block_to_string(
                "customers/customers.html",
                "body",
                context,
            )
            return HttpResponse(customer_list)
        else:
            customer_list = render_block_to_string(
                "customers/customers.html", "content", context
            )
            return HttpResponse(customer_list)

    return render(request, "customers/customers.html", context)


def customer_detail(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account").prefetch_related(
            Prefetch(
                "deposit_account__purchase_agreements",
                queryset=PurchaseAgreement.objects.select_related(
                    "account"
                ).prefetch_related(
                    Prefetch(
                        "agreement_line_items",
                        queryset=PurchaseAgreementLineItem.objects.filter(
                            is_current_version=True
                        ).select_related("product"),
                    )
                ),
            ),
            Prefetch(
                "deposit_account__cfa_agreements",
                queryset=CfaAgreement.objects.select_related("account"),
            ),
            Prefetch(
                "deposit_account__transactions",
                queryset=Transaction.objects.order_by("-created_at"),
            ),
            Prefetch("customer_sales", queryset=Sale.objects.order_by("-sale_date")),
        ),
        pk=pk,
    )

    customer_list = (
        Customer.objects.select_related("deposit_account")
        .only(
            "customer_id",
            "customer_number",
            "full_name",
            "deposit_account__cached_total_balance",
        )
        .order_by("-deposit_account__cached_total_balance")
    )

    search_query = request.GET.get("q", "")
    if search_query:
        customer_list = customer_list.filter(
            Q(full_name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(customer_id__icontains=search_query)
        )

    # Pagination
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    paginator = Paginator(customer_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    product_summary = {}

    line_items = (
        PurchaseAgreementLineItem.objects.filter(
            purchase_agreement__account__customer=customer,
            is_current_version=True,
        )
        .exclude(purchase_agreement__status=PurchaseAgreement.Status.CANCELLED)
        .exclude(status=PurchaseAgreementLineItem.Status.VOIDED)
        .select_related("product")
        .annotate(
            total_boxed_fulfilled=Coalesce(
                Sum(
                    "boxed_sales__quantity",
                    filter=Q(boxed_sales__sale__status=Sale.Status.ACTIVE),
                ),
                0,
            ),
            total_coupled_fulfilled=Coalesce(
                Count(
                    "coupled_sales",
                    filter=Q(coupled_sales__sale__status=Sale.Status.ACTIVE),
                    distinct=True,
                ),
                0,
            ),
        )
    )

    for item in line_items:
        # Get Model Name
        model_name = (
            item.product.modelname.upper()
            if item.product and item.product.modelname
            else "UNKNOWN PRODUCT"
        )

        if model_name not in product_summary:
            product_summary[model_name] = {
                "ordered": 0,
                "fulfilled": 0,
                "unfulfilled": 0,
            }

        # Calculate quantities using the annotated values
        ordered = item.quantity_ordered
        fulfilled = item.total_boxed_fulfilled + item.total_coupled_fulfilled

        product_summary[model_name]["ordered"] += ordered
        product_summary[model_name]["fulfilled"] += fulfilled

    # Calculate 'unfulfilled' and percentage
    for model, data in product_summary.items():
        data["unfulfilled"] = max(0, data["ordered"] - data["fulfilled"])

        if data["ordered"] > 0:
            data["percent"] = int((data["fulfilled"] / data["ordered"]) * 100)
        else:
            data["percent"] = 0

    context = {
        "customer": customer,
        "customer_list": page_obj,
        "product_summary": product_summary,
        "search_query": search_query,
    }

    if request.htmx:
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "customers/customer_detail.html",
                "main_content",
                context,
                request=request,
            )
            return HttpResponse(html)

        elif request.htmx.target == "main_body":
            html = render_block_to_string(
                "customers/customer_detail.html",
                "content",
                context,
                request=request,
            )
            return HttpResponse(html)

        else:
            html = render_block_to_string(
                "customers/customer_detail.html",
                "side_bar_list",
                context,
                request=request,
            )
            return HttpResponse(html)
    else:
        return render(request, "customers/customer_detail.html", context)


@require_GET
def filter_agreements_partial(request, pk):

    customer = get_object_or_404(Customer, pk=pk)
    agreements = customer.deposit_account.purchase_agreements.all()

    status_filter = request.GET.get("status")
    if status_filter:
        agreements = agreements.filter(status=status_filter)

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = ["created_at", "status", "purchase_agreement_number"]

    if direction == "desc":
        order_by_field = f"-{sort_field}"
    else:
        order_by_field = sort_field

    if sort_field in allowed_sort_fields:
        agreements = agreements.order_by(order_by_field)

    context = {
        "agreements": agreements,
        "pk": pk,  # Pass pk for hx-get url construction
        "sort_field": sort_field,
        "direction": direction,
    }

    return render(request, "customers/partials/purchase_agreements_list.html", context)


@require_GET
def filter_cfa_agreements_partial(request, pk):

    customer = get_object_or_404(Customer, pk=pk)
    agreements = customer.deposit_account.cfa_agreements.all()

    status_filter = request.GET.get("status")
    if status_filter:
        agreements = agreements.filter(status=status_filter)

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = [
        "created_at",
        "status",
        "cfa_agreement_number",
        "amount_allocated",
    ]

    if direction == "desc":
        order_by_field = f"-{sort_field}"
    else:
        order_by_field = sort_field

    if sort_field in allowed_sort_fields:
        agreements = agreements.order_by(order_by_field)

    context = {
        "cfas": agreements,
        "pk": pk,
        "sort_field": sort_field,
        "direction": direction,
    }

    return render(request, "customers/partials/cfa_agreements_list.html", context)


def manage_customers(request, pk=None):
    instance = get_object_or_404(Customer, pk=pk) if pk else None

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=instance)
        if form.is_valid():
            with transaction.atomic():
                form = form.save(commit=False)
                if not instance:
                    form.created_by = request.user
                form.updated_by = request.user
                form.save()
            return redirect("customers")

    else:
        form = CustomerForm(instance=instance)
    if instance:
        form_acion_url = reverse("edit_customer", kwargs={"pk": instance.pk})
    else:
        form_acion_url = reverse("add_customer")

    context = {
        "form": form,
        "form_action_url": form_acion_url,
        "instance": instance,
    }
    if request.htmx:
        html = render_block_to_string(
            "customers/customer_form.html", "content", context, request=request
        )
        return HttpResponse(html)
    return render(request, "customers/customer_form.html", context)


def customer_transactions(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    customer_pk = request.GET.get("customer")
    search_query = request.GET.get("q", "")

    transaction_list = Transaction.objects.select_related("account__customer").all()

    if request.GET.get("customer"):
        transaction_list = transaction_list.filter(account__customer__pk=customer_pk)

    if search_query:
        transaction_list = transaction_list.filter(
            Q(reference_number__icontains=search_query)
            | Q(account__customer__full_name__icontains=search_query)
            | Q(note__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = [
        "created_at",
        "account__customer__full_name",
        "amount",
        "transaction_type",
        "reference_number",
    ]

    if direction == "desc":
        order_by_field = f"-{sort_field}"
    else:
        order_by_field = sort_field

    if sort_field in allowed_sort_fields:
        transaction_list = transaction_list.order_by(order_by_field)

    paginator = Paginator(transaction_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "transactions": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if request.GET.get("page") or request.GET.get("q") or request.GET.get("sort"):
            transaction_list = render_block_to_string(
                "customers/customer_transactions.html",
                "body",
                context,
            )
            return HttpResponse(transaction_list)
        else:
            transaction_list = render_block_to_string(
                "customers/customer_transactions.html", "content", context
            )
            return HttpResponse(transaction_list)

    return render(request, "customers/customer_transactions.html", context)


def manage_transactions(request):
    initial_data = {}
    customer_pk = request.GET.get("customer")
    if customer_pk:
        account = get_object_or_404(DepositAccount, customer__pk=customer_pk)
        initial_data["account"] = account

    txn_type = request.GET.get("type")
    if txn_type:
        initial_data["transaction_type"] = txn_type

    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            txn_type = form.cleaned_data.get("transaction_type")
            if txn_type == Transaction.TransactionType.DEPOSIT:
                txn = customer_services.record_deposit(
                    account=form.cleaned_data["account"],
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data["note"],
                    user=request.user,
                    request=request,
                )
            else:
                with transaction.atomic():
                    txn = form.save(commit=False)
                    txn.created_by = request.user
                    txn.updated_by = request.user
                    txn.save()
                    customer_services._refresh_balances(txn.account)

            if customer_pk:
                return redirect("customer_detail", pk=customer_pk)
            return redirect("transaction_list")

    else:
        form = TransactionForm(initial=initial_data)
    context = {"form": form, "form_action_url": request.get_full_path()}

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "customers/customer_transaction_form.html",
                "content",
                context,
                request=request,
            )
        )
    return render(request, "customers/customer_transaction_form.html", context)


@require_POST
def void_transaction(request, pk):
    txn = get_object_or_404(Transaction, pk=pk)

    try:
        customer_services.void_deposit(pk, "", request.user, request=request)

        transaction_row = render_block_to_string(
            "customers/customer_transactions.html",
            "transaction_row",
            {"transaction": txn},
        )

        toast = render_to_string(
            "partials/toast.html",
            {
                "message": f"Transaction {txn.reference_number} voided successfully.",
                "type": "success",
            },
        )

        return HttpResponse(transaction_row + toast)

    except (ValidationError, customer_services.BusinessRuleViolation) as e:
        error_message = (
            e.message_dict.get("__all__", [str(e)])[0]
            if hasattr(e, "message_dict")
            else str(e)
        )

        toast = render_to_string(
            "partials/toast.html",
            {
                "message": error_message,
                "type": "error",
            },
        )

        response = HttpResponse(toast)
        response["HX-Reswap"] = "none"

        return response


def manage_purchase_agreements(request, pk=None):
    initial_data = {}
    customer_pk = request.GET.get("customer")
    if customer_pk:
        account = get_object_or_404(DepositAccount, customer__pk=customer_pk)
        initial_data["account"] = account

    instance = get_object_or_404(PurchaseAgreement, pk=pk) if pk else None
    qs = (
        instance.agreement_line_items.all()
        if instance
        else PurchaseAgreementLineItem.objects.none()
    )

    if request.method == "POST":
        form = PurchaseAgreementForm(request.POST, instance=instance)
        if form.is_valid():
            account = form.cleaned_data.get("account")
            balance = account.available_balance

            formset = PurchaseAgreementLineItemFormSet(
                request.POST, queryset=qs, prefix="item", available_balance=balance
            )
            if formset.is_valid():
                if not instance:
                    items = formset.save(commit=False)
                    line_items_data = [
                        {
                            'product': item.product,
                            'quantity_ordered': item.quantity_ordered,
                            'price_per_unit': item.price_per_unit,
                        }
                        for item in items
                    ]
                    agreement = customer_services.create_purchase_agreement(
                        account=account,
                        line_items_data=line_items_data,
                        user=request.user,
                        request=request,
                    )
                else:
                    with transaction.atomic():
                        agreement = form.save(commit=False)
                        agreement.created_by = request.user
                        agreement.updated_by = request.user
                        agreement.save()

                        items = formset.save(commit=False)
                        for obj in formset.deleted_objects:
                            obj.delete()

                        for item in items:
                            item.purchase_agreement = agreement
                            item.created_by = request.user
                            item.updated_by = request.user
                            item.save()

                        customer_services._refresh_balances(agreement.account)

                return redirect(agreement.account.customer.get_absolute_url)

        # Ensure formset exists for re-rendering if validation failed
        if 'formset' not in locals():
            formset = PurchaseAgreementLineItemFormSet(
                request.POST, queryset=qs, prefix="item"
            )

    else:
        form = PurchaseAgreementForm(initial=initial_data, instance=instance)
        formset = PurchaseAgreementLineItemFormSet(queryset=qs, prefix="item")

    form_action_url = (
        reverse("edit_purchase_agreement", kwargs={"pk": pk})
        if instance
        else reverse("add_purchase_agreement")
    )
    context = {
        "form": form,
        "formset": formset,
        "form_action_url": form_action_url,
        "is_creating": instance,
    }

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "customers/purchase_agreement_form.html",
                "content",
                context,
                request=request,
            )
        )

    return render(request, "customers/purchase_agreement_form.html", context)


def manage_purchase_agreement_line_item(request):
    try:
        current_index = int(request.GET.get("index", "0"))
    except ValueError:
        current_index = 0

    formset = PurchaseAgreementLineItemFormSet(prefix="item")
    empty_form = formset.empty_form
    empty_form.prefix = f"item-{current_index}"

    context = {"form": empty_form}
    return render(
        request, "customers/partials/purchase_agreement_line_item_form.html", context
    )


@require_POST
def cancel_purchase_agreement(request, pk):
    agreement = get_object_or_404(PurchaseAgreement, pk=pk)
    oob_content = ""

    try:
        customer_services.cancel_agreement(pk, request.user, request=request)

        toast = render_to_string(
            "partials/toast.html",
            {
                "message": f"Agreement {agreement.purchase_agreement_number} cancelled successfully.",
                "type": "success",
            },
            request=request,
        )
        oob_content += toast

        customer = agreement.account.customer
        wallet = render_to_string(
            "customers/partials/customer_wallet.html",
            {
                "customer": customer,
                "oob_swap_enabled": True,
            },
            request=request,
        )
        oob_content += wallet
    except customer_services.BusinessRuleViolation as e:
        toast = render_to_string(
            "partials/toast.html",
            {"message": str(e), "type": "error"},
            request=request,
        )
        oob_content += toast

    return HttpResponse(oob_content)


def manage_cfa_agreements(request, pk=None):
    initial_data = {}
    customer_pk = request.GET.get("customer")

    if customer_pk:
        account = get_object_or_404(DepositAccount, customer__pk=customer_pk)
        initial_data["account"] = account

    instance = get_object_or_404(CfaAgreement, pk=pk) if pk else None

    if request.method == "POST":
        form = CfaAgreementForm(request.POST, instance=instance)

        if form.is_valid():
            if not instance:
                cfa_agreement = customer_services.create_cfa_agreement(
                    account=form.cleaned_data["account"],
                    amount_naira=form.cleaned_data["amount_allocated"],
                    exchange_rate=form.cleaned_data["exchange_rate"],
                    user=request.user,
                    request=request,
                )
            else:
                with transaction.atomic():
                    cfa_agreement = form.save(commit=False)
                    cfa_agreement.updated_by = request.user
                    cfa_agreement.save()
                    customer_services._refresh_balances(cfa_agreement.account)

            return redirect(cfa_agreement.account.customer.get_absolute_url)

    else:
        form = CfaAgreementForm(initial=initial_data, instance=instance)

    form_action_url = (
        reverse("edit_cfa_agreement", kwargs={"pk": pk})
        if instance
        else reverse("add_cfa_agreement")
    )

    context = {"form": form, "form_action_url": form_action_url}

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "customers/cfa_agreement_form.html",
                "content",
                context,
                request=request,
            )
        )

    return render(request, "customers/cfa_agreement_form.html", context)


@require_POST
def cancel_cfa_agreement(request, pk):
    agreement = get_object_or_404(CfaAgreement, pk=pk)

    try:
        customer_services.cancel_cfa_agreement(pk, request.user, request=request)

        toast = render_to_string(
            "partials/toast.html",
            {
                "message": f"CFA Agreement {agreement.cfa_agreement_number} cancelled successfully.",
                "type": "success",
            },
        )

        wallet = render_to_string(
            "customers/partials/customer_wallet.html",
            {
                "customer": agreement.account.customer,
                "oob_swap_enabled": True,
            },
            request=request,
        )
        return HttpResponse(toast + wallet)
    except customer_services.BusinessRuleViolation as e:
        toast = render_to_string(
            "partials/toast.html",
            {"message": str(e), "type": "error"},
            request=request,
        )
        return HttpResponse(toast)


def manage_cfa_fulfillments(request):
    initial_data = {}
    cfa_agreement_pk = request.GET.get("agreement")
    if cfa_agreement_pk:
        agreement_instance = get_object_or_404(CfaAgreement, pk=cfa_agreement_pk)
        initial_data["cfa_agreement"] = agreement_instance

    if request.method == "POST":
        form = CfaFulfillmentForm(request.POST, initial=initial_data)

        if form.is_valid():
            try:
                fulfillment = form.save(commit=False)
                customer_services.record_cfa_fulfillment(
                    agreement_id=fulfillment.cfa_agreement.pk,
                    cfa_amount=fulfillment.cfa_amount_disbursed,
                    notes=fulfillment.notes,
                    user=request.user,
                    request=request,
                )

                return redirect(
                    fulfillment.cfa_agreement.account.customer.get_absolute_url
                )

            except Exception as e:
                error_message = (
                    f"An error occurred while saving the fulfillment: {e}",
                )
                logging.error(error_message, exc_info=True)
        else:
            print("Not Valid")
    else:
        form = CfaFulfillmentForm(initial=initial_data)

    context = {"form": form, "form_action_url": request.get_full_path()}

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "customers/cfa_fulfillment_form.html",
                "content",
                context,
                request=request,
            )
        )

    return render(request, "customers/cfa_fulfillment_form.html", context)


@require_POST
def void_cfa_fulfillment(request, pk):
    fulfillment = get_object_or_404(CfaFulfillment, pk=pk)

    try:
        customer_services.void_cfa_fulfillment(pk, "", request.user, request=request)

        toast = render_to_string(
            "partials/toast.html",
            {
                "message": f"Transaction {fulfillment.fulfillment_number} voided successfully.",
                "type": "success",
            },
        )

        wallet = render_to_string(
            "customers/partials/customer_wallet.html",
            {
                "customer": fulfillment.cfa_agreement.account.customer,
                "oob_swap_enabled": True,
            },
            request=request,
        )
        return HttpResponse(wallet + toast)
    except customer_services.BusinessRuleViolation as e:
        toast = render_to_string(
            "partials/toast.html",
            {"message": str(e), "type": "error"},
        )
        response = HttpResponse(toast)
        response["HX-Reswap"] = "none"
        return response


def sales(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    customer_pk = request.GET.get("customer")
    search_query = request.GET.get("q", "")
    sale_list = Sale.objects.annotate(
        total_boxed=Coalesce(
            Sum(
                F("boxed_sales__quantity") * F("boxed_sales__price"),
                output_field=DecimalField(),
            ),
            Value(0, output_field=DecimalField()),
        ),
        total_coupled=Coalesce(
            Sum("coupled_sales__price", output_field=DecimalField()),
            Value(0, output_field=DecimalField()),
        ),
    ).annotate(annotated_total=F("total_boxed") + F("total_coupled"))

    if customer_pk:
        sale_list = sale_list.filter(customer__pk=customer_pk)

    if search_query:
        sale_list = sale_list.filter(
            Q(sale_number__icontains=search_query)
            | Q(customer__full_name__icontains=search_query)
            | Q(customer__customer_number__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "sale_date")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = [
        "sale_date",
        "sale_number",
        "customer__full_name",
        "payment_method",
        "status",
        "sales_total",
    ]

    if direction == "desc":
        order_by_field = f"-{sort_field}"
    else:
        order_by_field = sort_field

    if sort_field == "sales_total":
        if direction == "desc":
            sale_list = sale_list.order_by("-annotated_total")
        else:
            sale_list = sale_list.order_by("annotated_total")
    elif sort_field in allowed_sort_fields:
        sale_list = sale_list.order_by(order_by_field)

    paginator = Paginator(sale_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "sales": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            sale_list = render_block_to_string(
                "customers/sales/sales.html",
                "body",
                context,
            )
            return HttpResponse(sale_list)
        else:
            sale_list = render_block_to_string(
                "customers/sales/sales.html", "content", context
            )
            return HttpResponse(sale_list)

    return render(request, "customers/sales/sales.html", context)


def sale_detail(request, pk):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)

    sale = get_object_or_404(
        Sale.objects.select_related(
            "customer", "created_by", "agreement"
        ).prefetch_related(
            "boxed_sales__product", "coupled_sales__transformation_item"
        ),
        pk=pk,
    )

    all_sales = Sale.objects.select_related("customer").order_by("-sale_date")

    search_query = request.GET.get("q", "")
    if search_query:
        all_sales = all_sales.filter(
            Q(sale_number__icontains=search_query)
            | Q(customer__full_name__icontains=search_query)
            | Q(customer__customer_id__icontains=search_query)
        )

    paginator = Paginator(all_sales, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "sale": sale,
        "sale_list": page_obj,
        "search_query": search_query,
    }

    if request.htmx:
        # If clicking a link in the sidebar, update the Main Content area
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "customers/sales/sale_detail.html",
                "main_content",
                context,
            )
            return HttpResponse(html)

        # If performing a full hx-boost navigation
        elif request.htmx.target == "main_body":
            html = render_block_to_string(
                "customers/sales/sale_detail.html", "content", context
            )
            return HttpResponse(html)

        # If using pagination in the sidebar
        else:
            html = render_block_to_string(
                "customers/sales/sale_detail.html", "side_bar_list", context
            )
            return HttpResponse(html)

    else:
        return render(request, "customers/sales/sale_detail.html", context)


def search_customers(request):
    query = request.GET.get("q", "")
    customers = []
    if query:
        customers = Customer.objects.filter(
            Q(full_name__icontains=query)
            | Q(phone__icontains=query)
            | Q(customer_number__icontains=query)
        )[:10]
    return render(
        request, "partials/search_results_customer.html", {"customers": customers}
    )


def search_products(request):
    query = request.GET.get("q", "")
    products = []
    if query:
        products = Product.objects.filter(
            Q(modelname__icontains=query)
            | Q(sku__icontains=query)
            | Q(brand__name__icontains=query),
            type_variant=Product.TypeVariant.BOXED,
        ).select_related("brand")[:10]
    return render(
        request, "partials/search_results_product.html", {"products": products}
    )


def search_transformation_items(request):
    query = request.GET.get("q", "")
    items = []
    if query:
        items = TransformationItem.objects.filter(
            Q(item_number__icontains=query)
            | Q(engine_number__icontains=query)
            | Q(chassis_number__icontains=query)
            | Q(target_product__brand__name__icontains=query)
            | Q(target_product__modelname__icontains=query),
            status=TransformationItem.Status.AVAILABLE,
        ).select_related("target_product")[:10]
    return render(
        request, "partials/search_results_transformation_item.html", {"items": items}
    )


def record_sale(request):
    selected_customer = None  # Initialize for context

    if request.method == "POST":
        form = RecordSaleForm(request.POST)

        # Determine if this is a "from deposit" sale
        payment_method = request.POST.get("payment_method", "")
        is_from_deposit = payment_method == Sale.PaymentMethod.FROM_DEPOSIT

        # Always create formsets with POST data for validation and re-rendering
        boxed_formset = BoxedSaleFormSet(
            request.POST, prefix="boxed", is_from_deposit=is_from_deposit
        )
        coupled_formset = CoupledSaleFormSet(
            request.POST, prefix="coupled", is_from_deposit=is_from_deposit
        )

        # Try to get the selected customer from the POST data for re-rendering
        customer_pk = request.POST.get("customer")
        if customer_pk:
            try:
                selected_customer = Customer.objects.get(pk=customer_pk)
            except Customer.DoesNotExist:
                pass

        # Filter agreement_line_item queryset based on selected agreement
        agreement_pk = request.POST.get("agreement")
        if agreement_pk:
            line_items_qs = PurchaseAgreementLineItem.objects.filter(
                purchase_agreement__pk=agreement_pk,
                is_current_version=True,
                status__in=[
                    PurchaseAgreementLineItem.Status.ACTIVE,
                    PurchaseAgreementLineItem.Status.PARTIALLY_FULFILLED,
                ],
            ).select_related("product")

            # Apply the filtered queryset to each form in the formsets
            for formset_form in boxed_formset.forms:
                formset_form.fields["agreement_line_item"].queryset = line_items_qs
            for formset_form in coupled_formset.forms:
                formset_form.fields["agreement_line_item"].queryset = line_items_qs

        # Validate all forms before saving anything
        form_valid = form.is_valid()
        boxed_valid = boxed_formset.is_valid()
        coupled_valid = coupled_formset.is_valid()

        if form_valid and boxed_valid and coupled_valid:
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.created_by = request.user
                sale.updated_by = request.user

                # Re-bind formsets with the sale instance for saving
                boxed_formset = BoxedSaleFormSet(
                    request.POST,
                    instance=sale,
                    prefix="boxed",
                    is_from_deposit=is_from_deposit,
                )
                coupled_formset = CoupledSaleFormSet(
                    request.POST,
                    instance=sale,
                    prefix="coupled",
                    is_from_deposit=is_from_deposit,
                )

                boxed_formset.is_valid()
                coupled_formset.is_valid()

                boxed_items = boxed_formset.save(commit=False)
                for item in boxed_items:
                    item.created_by = request.user
                    item.updated_by = request.user

                coupled_items = coupled_formset.save(commit=False)
                for item in coupled_items:
                    item.created_by = request.user
                    item.updated_by = request.user

                # Call service to handle all business logic
                customer_services.create_sale(
                    sale, boxed_items, coupled_items, request.user
                )

                messages.success(
                    request, f"Sale {sale.sale_number} recorded successfully."
                )
                if request.htmx:
                    return HttpResponseClientRedirect(reverse("sales"))
                return redirect("sales")
        else:
            # Form validation failed - errors will be displayed in template
            if not form_valid:
                messages.error(request, "Please correct the errors in the sale form.")
            if not boxed_valid or not coupled_valid:
                messages.error(request, "Please correct the errors in the sale items.")

    else:
        # Check for customer query param (from customer detail page)
        customer_pk = request.GET.get("customer")
        initial = {}

        if customer_pk:
            try:
                selected_customer = Customer.objects.get(pk=customer_pk)
                initial["customer"] = customer_pk
            except Customer.DoesNotExist:
                pass

        form = RecordSaleForm(initial=initial)

        # If customer is preselected, load their agreements
        if selected_customer:
            form.fields["agreement"].queryset = PurchaseAgreement.objects.filter(
                account__customer=selected_customer,
                status__in=[
                    PurchaseAgreement.Status.ACTIVE,
                    PurchaseAgreement.Status.PARTIALLY_FULFILLED,
                ],
            )

        boxed_formset = BoxedSaleFormSet(prefix="boxed")
        coupled_formset = CoupledSaleFormSet(prefix="coupled")

    context = {
        "form": form,
        "boxed_formset": boxed_formset,
        "coupled_formset": coupled_formset,
        "selected_customer": selected_customer,
    }

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "customers/sales/record_sale.html", "content", context, request=request
            )
        )

    return render(request, "customers/sales/record_sale.html", context)


def load_customer_agreements(request):
    """
    HTMX view to return options for Agreement Select based on Customer.
    """
    customer_pk = request.GET.get("customer")
    agreements = PurchaseAgreement.objects.none()

    if customer_pk:
        agreements = PurchaseAgreement.objects.filter(
            account__customer__pk=customer_pk,
            status__in=[
                PurchaseAgreement.Status.ACTIVE,
                PurchaseAgreement.Status.PARTIALLY_FULFILLED,
            ],
        )

    return render(
        request, "customers/partials/agreement_options.html", {"agreements": agreements}
    )


def load_agreement_line_items(request):
    """
    HTMX view to return options for Agreement Line Items based on selected Agreement.
    Returns line items that still have remaining quantity to fulfill.
    """
    agreement_pk = request.GET.get("agreement")
    line_items = PurchaseAgreementLineItem.objects.none()

    if agreement_pk:
        line_items = PurchaseAgreementLineItem.objects.filter(
            purchase_agreement__pk=agreement_pk,
            is_current_version=True,
            status__in=[
                PurchaseAgreementLineItem.Status.ACTIVE,
                PurchaseAgreementLineItem.Status.PARTIALLY_FULFILLED,
            ],
        ).select_related("product")

    return render(
        request,
        "customers/partials/agreement_line_item_options.html",
        {"line_items": line_items},
    )


@require_POST
def void_sale(request, pk):
    sale = get_object_or_404(Sale, pk=pk)
    void_reason = request.POST.get("void_reason", "")

    try:
        customer_services.void_sale(pk, void_reason, request.user, request=request)
        messages.success(request, f"Sale {sale.sale_number} voided successfully.")
    except customer_services.BusinessRuleViolation as e:
        messages.error(request, str(e))

    return redirect("sale_detail", pk=pk)
