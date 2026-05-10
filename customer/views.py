from decimal import Decimal, InvalidOperation
from django.shortcuts import render, get_object_or_404, redirect
from render_block import render_block_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import HttpResponse
from django_htmx.http import HttpResponseClientRedirect
from django.db.models import Prefetch, Sum, F, DecimalField, Value, Q, Count
from django.db.models.functions import Coalesce
from django.utils import timezone
from .utils import parse_backdate
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
from inventory.models import TransformationItem
from .forms import (
    CustomerForm,
    TransactionForm,
    PurchaseAgreementForm,
    PurchaseAgreementLineItemForm,
    PurchaseAgreementLineItemFormSet,
    CfaAgreementForm,
    CfaFulfillmentForm,
    NormalSaleForm,
    RecordSaleForm,
    AgreementSaleForm,
    BoxedSaleFormSet,
    CoupledSaleFormSet,
    AmendLineItemForm,
)
from . import services as customer_services
from inventory.models import Product, TransformationItem
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.db import transaction
import logging

logger = logging.getLogger(__name__)



def customers(request):
    search_query = request.GET.get("q", "")
    filter_by = request.GET.get("filter", "")
    sort_by = request.GET.get("sort", "name_asc")

    customer_list = (
        Customer.objects.annotate(
            total_balance=Coalesce(
                F("deposit_account__cached_total_balance"),
                Value(0),
                output_field=DecimalField(),
            ),
            allocated_balance=Coalesce(
                F("deposit_account__cached_allocated_balance"),
                Value(0),
                output_field=DecimalField(),
            ),
            available_balance=Coalesce(
                F("deposit_account__cached_available_balance"),
                Value(0),
                output_field=DecimalField(),
            ),
            active_agreement_count=Count(
                "deposit_account__purchase_agreements",
                filter=Q(
                    deposit_account__purchase_agreements__status=PurchaseAgreement.Status.ACTIVE
                ),
                distinct=True,
            ),
            cfa_agreement_count=Count(
                "deposit_account__cfa_agreements",
                filter=Q(
                    deposit_account__cfa_agreements__status=CfaAgreement.Status.ACTIVE
                ),
                distinct=True,
            ),
            sale_count=Count("customer_sales", distinct=True),
        )
        .select_related("deposit_account")
        .order_by("-deposit_account__cached_total_balance")
    )

    # search
    if search_query:
        customer_list = customer_list.filter(
            Q(full_name__icontains=search_query)
            | Q(phone__icontains=search_query)
            | Q(customer_number__icontains=search_query)
        )

    # filtering
    match filter_by:
        case "active_agreements":
            customer_list = customer_list.filter(
                Q(
                    deposit_account__purchase_agreements__status=PurchaseAgreement.Status.ACTIVE
                )
                | Q(deposit_account__cfa_agreements__status=CfaAgreement.Status.ACTIVE)
            ).distinct()
        case "balance_gt_1m":
            customer_list = customer_list.filter(available_balance__gt=1_000_000)
        case "no_activity":
            customer_list = customer_list.filter(
                deposit_account__transactions__isnull=True,
                customer_sales__isnull=True,
            )

    # sorting
    match sort_by:
        case "balance_desc":
            customer_list = customer_list.order_by("-total_balance")
        case "newest":
            customer_list = customer_list.order_by("-created_at")
        case _:
            customer_list = customer_list.order_by("full_name")

    # pagination
    PAGE_SIZE = 20
    paginator = Paginator(customer_list, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # total deposited for subtitle
    total_deposited = customer_list.aggregate(
        total=Coalesce(Sum("total_balance"), Value(0), output_field=DecimalField())
    )["total"] or Decimal("0.00")

    params = {}
    if search_query:
        params["q"] = search_query
    if filter_by:
        params["filter"] = filter_by
    if sort_by and sort_by != "name_asc":
        params["sort"] = sort_by

    context = {
        "customers": page_obj,
        "search_query": search_query,
        "filter_by": filter_by,
        "sort_by": sort_by,
        "total_deposited": total_deposited,
        "params": params,
    }

    if request.htmx:
        if any(key in request.GET for key in ["page", "q", "filter", "sort"]):
            return render(
                request,
                "customers/customers.html#customerlist-table-partial",
                context,
            )
        else:

            return render(
                request,
                "customers/customers.html#customer-list-partial",
                context,
            )

    return render(request, "customers/customers.html", context)


def customer_detail(request, pk):
    active_tab = request.GET.get("tab", "agreements")

    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"),
        pk=pk,
    )

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

        ordered = item.quantity_ordered
        fulfilled = item.total_boxed_fulfilled + item.total_coupled_fulfilled

        product_summary[model_name]["ordered"] += ordered
        product_summary[model_name]["fulfilled"] += fulfilled

    for model, data in product_summary.items():
        data["unfulfilled"] = max(0, data["ordered"] - data["fulfilled"])

        if data["ordered"] > 0:
            data["percent"] = int((data["fulfilled"] / data["ordered"]) * 100)
        else:
            data["percent"] = 0

    agreements = (
        customer.deposit_account.purchase_agreements.select_related("account")
        .prefetch_related(
            Prefetch(
                "agreement_line_items",
                queryset=PurchaseAgreementLineItem.objects.filter(
                    is_current_version=True
                ).select_related("product"),
            )
        )
        .order_by("-created_at")
    )

    cfa_agreements = (
        customer.deposit_account.cfa_agreements.select_related("account")
        .prefetch_related("cfa_fulfillments")
        .order_by("-created_at")
    )

    transactions = customer.deposit_account.transactions.all().order_by("-created_at")[
        :20
    ]

    sales = (
        customer.customer_sales.select_related("agreement")
        .prefetch_related(
            "boxed_sales__product", "coupled_sales__transformation_item__target_product"
        )
        .order_by("-sale_date")[:20]
    )

    account = customer.deposit_account
    total_balance = account.cached_total_balance or Decimal("0.00")
    allocated_balance = account.cached_allocated_balance or Decimal("0.00")
    available_balance = account.cached_available_balance or Decimal("0.00")

    committed_pct = (
        int((allocated_balance / total_balance) * 100) if total_balance > 0 else 0
    )
    available_pct = 100 - committed_pct if total_balance > 0 else 100

    active_agreement_count = (
        agreements.exclude(status=PurchaseAgreement.Status.CANCELLED)
        .exclude(status=PurchaseAgreement.Status.FULFILLED)
        .count()
    )

    context = {
        "customer": customer,
        "active_tab": active_tab,
        "product_summary": product_summary,
        "agreements": agreements,
        "cfa_agreements": cfa_agreements,
        "transactions": transactions,
        "sales": sales,
        "total_balance": total_balance,
        "allocated_balance": allocated_balance,
        "available_balance": available_balance,
        "committed_pct": committed_pct,
        "available_pct": available_pct,
        "active_agreement_count": active_agreement_count,
    }

    if request.htmx:
        if request.htmx.target == "tab_area":
            return render(
                request,
                "customers/partials/tab_area_partial.html",
                context,
            )
        else:
            return render(
                request,
                "customers/customer_detail.html#customer-detail-partial",
                context,
            )
    return render(request, "customers/customer_detail.html", context)


def modal_deposit(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"), pk=pk
    )

    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            try:
                custom_date = parse_backdate(request.POST.get("date"))
                customer_services.record_deposit(
                    account=customer.deposit_account,
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data.get("note", ""),
                    user=request.user,
                    request=request,
                    created_at=custom_date,
                )
                messages.success(
                    request,
                    f"Deposit of ₦{form.cleaned_data['amount']:,.0f} recorded for {customer.full_name}.",
                )
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = TransactionForm()

    return render(
        request,
        "customers/modals/deposit_modal.html",
        {
            "customer": customer,
            "form": form,
        },
    )


def modal_withdrawal(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"), pk=pk
    )

    if request.method == "POST":
        form = TransactionForm(request.POST)
        if form.is_valid():
            try:
                custom_date = parse_backdate(request.POST.get("date"))
                customer_services.record_withdrawal(
                    account=customer.deposit_account,
                    amount=form.cleaned_data["amount"],
                    note=form.cleaned_data.get("note", ""),
                    user=request.user,
                    request=request,
                    created_at=custom_date,
                )
                messages.success(
                    request,
                    f"Withdrawal of ₦{form.cleaned_data['amount']:,.0f} recorded for {customer.full_name}.",
                )
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = TransactionForm()

    return render(
        request,
        "customers/modals/withdrawal_modal.html",
        {
            "customer": customer,
            "form": form,
        },
    )


def modal_cfa_agreement(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("deposit_account"), pk=pk
    )

    if request.method == "POST":
        form = CfaAgreementForm(request.POST)
        if form.is_valid():
            try:
                customer_services.create_cfa_agreement(
                    account=customer.deposit_account,
                    amount_naira=form.cleaned_data["amount_allocated"],
                    exchange_rate=form.cleaned_data["exchange_rate"],
                    user=request.user,
                    request=request,
                )
                messages.success(
                    request,
                    f"CFA agreement created for {customer.full_name}.",
                )
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = CfaAgreementForm(initial={"account": customer.deposit_account})

    return render(
        request,
        "customers/modals/cfa_agreement_modal.html",
        {
            "customer": customer,
            "form": form,
        },
    )


def modal_cfa_agreement_edit(request, pk):
    cfa_agreement = get_object_or_404(
        CfaAgreement.objects.select_related("account__customer", "account"), pk=pk
    )
    customer = cfa_agreement.account.customer
    # Available balance excluding this agreement's current allocation
    available_balance = (
        cfa_agreement.account.available_balance + cfa_agreement.amount_allocated
    )

    if request.method == "POST":
        form = CfaAgreementForm(request.POST, instance=cfa_agreement)
        if form.is_valid():
            try:
                with transaction.atomic():
                    cfa_agreement.amount_allocated = form.cleaned_data[
                        "amount_allocated"
                    ]
                    cfa_agreement.exchange_rate = form.cleaned_data["exchange_rate"]
                    cfa_agreement.updated_by = request.user
                    cfa_agreement.full_clean()
                    cfa_agreement.save()
                    customer_services._refresh_balances(cfa_agreement.account)
                messages.success(request, "CFA agreement updated.")
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = CfaAgreementForm(
            instance=cfa_agreement,
            initial={"account": cfa_agreement.account},
        )

    return render(
        request,
        "customers/modals/cfa_agreement_edit_modal.html",
        {
            "cfa_agreement": cfa_agreement,
            "customer": customer,
            "form": form,
            "available_balance": available_balance,
        },
    )


def modal_cancel_cfa_agreement(request, pk):
    cfa_agreement = get_object_or_404(
        CfaAgreement.objects.select_related("account__customer"), pk=pk
    )
    customer = cfa_agreement.account.customer

    if request.method == "POST":
        try:
            customer_services.cancel_cfa_agreement(pk, request.user, request=request)
            messages.warning(
                request,
                f"CFA agreement {cfa_agreement.cfa_agreement_number} cancelled.",
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "customerDetailChanged"
            return response

        except (ValidationError, customer_services.BusinessRuleViolation) as e:
            error_msg = str(e)
            if hasattr(e, "message_dict"):
                error_msg = "; ".join(
                    f"{field}: {msgs[0]}" if isinstance(msgs, list) else str(msgs)
                    for field, msgs in e.message_dict.items()
                )
            return render(
                request,
                "customers/modals/cancel_cfa_agreement_modal.html",
                {
                    "cfa_agreement": cfa_agreement,
                    "customer": customer,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "customers/modals/cancel_cfa_agreement_modal.html",
        {
            "cfa_agreement": cfa_agreement,
            "customer": customer,
        },
    )


def modal_void_transaction(request, pk):
    txn = get_object_or_404(
        Transaction.objects.select_related("account__customer"), pk=pk
    )
    customer = txn.account.customer

    if request.method == "POST":
        void_reason = request.POST.get("void_reason", "")
        try:
            customer_services.void_deposit(
                pk, void_reason, request.user, request=request
            )
            messages.success(
                request, f"Transaction {txn.reference_number} voided successfully."
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "customerDetailChanged"
            return response

        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "message_dict"):
                error_msg = "; ".join(
                    f"{field}: {msgs[0]}" if isinstance(msgs, list) else str(msgs)
                    for field, msgs in e.message_dict.items()
                )
            return render(
                request,
                "customers/modals/void_transaction_modal.html",
                {
                    "txn": txn,
                    "customer": customer,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "customers/modals/void_transaction_modal.html",
        {
            "txn": txn,
            "customer": customer,
        },
    )


def modal_cfa_fulfillment(request, pk):
    cfa_agreement = get_object_or_404(
        CfaAgreement.objects.select_related("account__customer"), pk=pk
    )
    customer = cfa_agreement.account.customer

    if request.method == "POST":
        form = CfaFulfillmentForm(request.POST)
        if form.is_valid():
            try:
                custom_date = parse_backdate(request.POST.get("date"))
                customer_services.record_cfa_fulfillment(
                    agreement_id=cfa_agreement.pk,
                    cfa_amount=form.cleaned_data["cfa_amount_disbursed"],
                    notes=form.cleaned_data.get("notes", ""),
                    user=request.user,
                    request=request,
                    created_at=custom_date,
                )
                messages.success(request, "Disbursement recorded.")
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = CfaFulfillmentForm()

    return render(
        request,
        "customers/modals/cfa_fulfillment_modal.html",
        {
            "cfa_agreement": cfa_agreement,
            "customer": customer,
            "form": form,
        },
    )


def modal_void_cfa_fulfillment(request, pk):
    fulfillment = get_object_or_404(
        CfaFulfillment.objects.select_related("cfa_agreement__account__customer"), pk=pk
    )
    customer = fulfillment.cfa_agreement.account.customer

    if request.method == "POST":
        void_reason = request.POST.get("void_reason", "")
        try:
            customer_services.void_cfa_fulfillment(
                pk, void_reason, request.user, request=request
            )
            messages.success(request, "Disbursement voided.")
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "customerDetailChanged"
            return response

        except Exception as e:
            error_msg = str(e)
            if hasattr(e, "message_dict"):
                error_msg = "; ".join(
                    f"{field}: {msgs[0]}" if isinstance(msgs, list) else str(msgs)
                    for field, msgs in e.message_dict.items()
                )
            return render(
                request,
                "customers/modals/void_cfa_fulfillment_modal.html",
                {
                    "fulfillment": fulfillment,
                    "customer": customer,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "customers/modals/void_cfa_fulfillment_modal.html",
        {
            "fulfillment": fulfillment,
            "customer": customer,
        },
    )


def modal_new_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                customer = form.save(commit=False)
                customer.created_by = request.user
                customer.updated_by = request.user
                customer.save()
            messages.success(
                request,
                f"Customer {customer.full_name} ({customer.customer_number}) created.",
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "customerCreated"
            return response
    else:
        form = CustomerForm()

    return render(
        request,
        "customers/modals/new_customer_modal.html",
        {
            "form": form,
        },
    )


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


def manage_purchase_agreements(request, pk=None):
    initial_data = {}
    customer_pk = request.GET.get("customer")
    if customer_pk:
        account = get_object_or_404(DepositAccount, customer__pk=customer_pk)
        initial_data["account"] = account

    instance = get_object_or_404(PurchaseAgreement, pk=pk) if pk else None
    if not instance:
        initial_data.setdefault("date", timezone.now().date())

    if request.method == "POST":
        form = PurchaseAgreementForm(request.POST, instance=instance)
        if form.is_valid():
            account = form.cleaned_data.get("account")
            balance = account.available_balance

            qs = (
                instance.agreement_line_items.filter(is_current_version=True)
                if instance
                else None
            )
            formset = PurchaseAgreementLineItemFormSet(
                request.POST,
                instance=instance,
                prefix="item",
                queryset=qs,
                available_balance=balance,
            )
            if formset.is_valid():
                if not instance:
                    items = formset.save(commit=False)
                    line_items_data = [
                        {
                            "product": item.product,
                            "quantity_ordered": item.quantity_ordered,
                            "price_per_unit": item.price_per_unit,
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
                        agreement.updated_by = request.user
                        agreement.save()

                        formset.instance = agreement
                        items = formset.save(commit=False)

                        for obj in formset.deleted_objects:
                            obj.delete()

                        for item in items:
                            item.created_by = request.user
                            item.updated_by = request.user
                            item.save()

                        customer_services._refresh_balances(agreement.account)

                messages.success(
                    request,
                    f"Agreement {agreement.purchase_agreement_number} saved successfully.",
                )
                return redirect("agreement_detail", pk=agreement.pk)
        else:
            qs = (
                instance.agreement_line_items.filter(is_current_version=True)
                if instance
                else None
            )
            formset = PurchaseAgreementLineItemFormSet(
                request.POST,
                instance=instance,
                prefix="item",
                queryset=qs,
            )

    else:
        form = PurchaseAgreementForm(initial=initial_data, instance=instance)
        qs = (
            instance.agreement_line_items.filter(is_current_version=True)
            if instance
            else None
        )
        formset = PurchaseAgreementLineItemFormSet(
            instance=instance,
            prefix="item",
            queryset=qs,
        )

    form_action_url = (
        reverse("edit_purchase_agreement", kwargs={"pk": pk})
        if instance
        else reverse("add_purchase_agreement")
    )

    customer = None
    if instance:
        customer = instance.account.customer
    elif customer_pk:
        customer = get_object_or_404(Customer, pk=customer_pk)
    elif request.method == "POST":
        account_pk = request.POST.get("account")
        if account_pk:
            try:
                account = DepositAccount.objects.select_related("customer").get(
                    pk=account_pk
                )
                customer = account.customer
            except DepositAccount.DoesNotExist:
                pass

    context = {
        "form": form,
        "formset": formset,
        "form_action_url": form_action_url,
        "is_creating": instance is None,
        "agreement": instance,
        "customer": customer,
    }
    if request.htmx:
        return render(
            request,
            "customers/purchase_agreement_form.html#agreement-form-partial",
            context,
        )
    return render(request, "customers/purchase_agreement_form.html", context)


def agreement_line_item_add(request):
    """
    Receives the full current form state via POST (hx-include="closest form").
    Appends one empty row by incrementing TOTAL_FORMS and seeding blank fields.
    Returns the re-rendered #formset-container partial.
    """
    post_data = request.POST.copy()
    total_forms = int(post_data.get("item-TOTAL_FORMS", 0))

    post_data[f"item-{total_forms}-product"] = ""
    post_data[f"item-{total_forms}-quantity_ordered"] = ""
    post_data[f"item-{total_forms}-price_per_unit"] = ""
    post_data["item-TOTAL_FORMS"] = total_forms + 1

    formset = PurchaseAgreementLineItemFormSet(post_data, prefix="item")

    return render(
        request,
        "customers/partials/purchase_agreement_formset.html",
        {"formset": formset},
    )


def agreement_line_item_remove(request, index):
    """
    Receives the full current form state via POST (hx-include="closest form")
    and the index of the row to operate on from the URL.

    Logic:
    - If the row has a pk (item-{index}-id is non-empty): the row is an
      existing DB record. Toggle its DELETE flag. If it was unmarked, mark it
      "on". If it was already "on", unmark it (undo).
    - If the row has no pk: it is a new unsaved row. Shift all rows above
      this index down by one, decrement TOTAL_FORMS, drop the row entirely.

    Returns the re-rendered #formset-container partial.
    """
    post_data = request.POST.copy()
    total_forms = int(post_data.get("item-TOTAL_FORMS", 0))
    pk_value = post_data.get(f"item-{index}-id", "").strip()

    if pk_value:
        # Existing DB record — toggle DELETE
        already_deleted = post_data.get(f"item-{index}-DELETE", "") == "on"
        if already_deleted:
            post_data.pop(f"item-{index}-DELETE", None)
        else:
            post_data[f"item-{index}-DELETE"] = "on"

        formset = PurchaseAgreementLineItemFormSet(post_data, prefix="item")

    else:
        # New unsaved row — remove by shifting indexes
        import urllib.parse
        from django.http import QueryDict

        line_fields = ["id", "product", "quantity_ordered", "price_per_unit", "DELETE"]
        new_data = {}
        new_index = 0

        for i in range(total_forms):
            if i == index:
                continue
            for field in line_fields:
                old_key = f"item-{i}-{field}"
                if old_key in post_data:
                    new_data[f"item-{new_index}-{field}"] = post_data[old_key]
            new_index += 1

        new_data["item-TOTAL_FORMS"] = new_index
        new_data["item-INITIAL_FORMS"] = post_data.get("item-INITIAL_FORMS", 0)
        new_data["item-MIN_NUM_FORMS"] = post_data.get("item-MIN_NUM_FORMS", 0)
        new_data["item-MAX_NUM_FORMS"] = post_data.get("item-MAX_NUM_FORMS", 1000)

        encoded = urllib.parse.urlencode(new_data, doseq=True)
        rebuilt = QueryDict(encoded, mutable=True)

        formset = PurchaseAgreementLineItemFormSet(rebuilt, prefix="item")

    return render(
        request,
        "customers/partials/purchase_agreement_formset.html",
        {"formset": formset},
    )


def modal_cancel_purchase_agreement(request, pk):
    agreement = get_object_or_404(
        PurchaseAgreement.objects.select_related("account__customer"), pk=pk
    )
    customer = agreement.account.customer

    if request.method == "POST":
        try:
            customer_services.cancel_agreement(pk, request.user, request=request)
            messages.warning(
                request,
                f"Agreement {agreement.purchase_agreement_number} cancelled.",
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "customerDetailChanged"
            return response

        except customer_services.BusinessRuleViolation as e:
            error_msg = str(e)
            return render(
                request,
                "customers/modals/cancel_purchase_agreement_modal.html",
                {
                    "agreement": agreement,
                    "customer": customer,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "customers/modals/cancel_purchase_agreement_modal.html",
        {
            "agreement": agreement,
            "customer": customer,
        },
    )


def modal_amend_line_item(request, pk):
    line_item = get_object_or_404(
        PurchaseAgreementLineItem.objects.select_related(
            "purchase_agreement__account__customer", "product"
        ),
        pk=pk,
    )
    agreement = line_item.purchase_agreement
    customer = agreement.account.customer
    fulfilled = line_item.quantity_fulfilled_accross_all_versions

    if request.method == "POST":
        form = AmendLineItemForm(request.POST, line_item=line_item)
        if form.is_valid():
            try:
                new_item = customer_services.amend_line_item(
                    line_item_id=line_item.pk,
                    new_quantity=form.cleaned_data["new_quantity"],
                    new_price_per_unit=form.cleaned_data["new_price_per_unit"],
                    reason=form.cleaned_data.get("reason", ""),
                    user=request.user,
                    request=request,
                )
                messages.success(
                    request,
                    f"Line item amended. Version {new_item.version} created.",
                )
                response = HttpResponse(status=204)
                response["HX-Trigger"] = "customerDetailChanged"
                return response

            except (ValidationError, customer_services.BusinessRuleViolation) as e:
                form.add_error(None, str(e))
    else:
        form = AmendLineItemForm(
            initial={
                "new_quantity": line_item.quantity_ordered,
                "new_price_per_unit": line_item.price_per_unit,
            },
            line_item=line_item,
        )

    return render(
        request,
        "customers/modals/amend_line_item_modal.html",
        {
            "line_item": line_item,
            "agreement": agreement,
            "customer": customer,
            "form": form,
            "fulfilled": fulfilled,
        },
    )


def agreement_detail(request, pk):
    agreement = get_object_or_404(
        PurchaseAgreement.objects.select_related(
            "account", "account__customer", "created_by"
        ),
        pk=pk,
    )
    customer = agreement.account.customer

    line_items = (
        agreement.agreement_line_items.select_related("product", "product__inventory")
        .prefetch_related(
            "boxed_sales",
            "boxed_sales__sale",
            "coupled_sales",
            "coupled_sales__sale",
            "coupled_sales__transformation_item",
        )
        .order_by("line_number")
    )

    # Build line item data with fulfillment details
    line_items_data = []
    for item in line_items:
        boxed_sales = item.boxed_sales.filter(sale__status=Sale.Status.ACTIVE)
        coupled_sales = item.coupled_sales.filter(
            sale__status=Sale.Status.ACTIVE
        ).select_related(
            "transformation_item", "transformation_item__transformation"
        )

        # Get all transformation items (coupled units) sold for this line item
        coupled_details = []
        for cs in coupled_sales:
            ti = cs.transformation_item
            coupled_details.append({
                "sale_pk": cs.sale.pk,
                "sale_number": cs.sale.sale_number,
                "sale_date": cs.sale.sale_date,
                "price": cs.price,
                "engine_number": ti.engine_number,
                "chassis_number": ti.chassis_number,
                "item_number": ti.item_number,
            })

        # Get boxed sales details
        boxed_details = []
        for bs in boxed_sales:
            boxed_details.append({
                "sale_pk": bs.sale.pk,
                "sale_number": bs.sale.sale_number,
                "sale_date": bs.sale.sale_date,
                "quantity": bs.quantity,
                "price": bs.price,
            })

        total_fulfilled = item.quantity_fulfilled_accross_all_versions
        remaining = item.remaining_quantity
        progress_pct = 0
        if item.quantity_ordered > 0:
            progress_pct = int((total_fulfilled / item.quantity_ordered) * 100)

        line_items_data.append({
            "item": item,
            "boxed_details": boxed_details,
            "coupled_details": coupled_details,
            "total_fulfilled": total_fulfilled,
            "remaining": remaining,
            "progress_pct": progress_pct,
            "line_total": item.total_line,
            "fulfilled_value": total_fulfilled * item.price_per_unit,
            "remaining_value": remaining * item.price_per_unit,
        })

    # Check for superseded (old version) line items
    superseded_items = (
        agreement.agreement_line_items.filter(is_current_version=False)
        .select_related("product")
        .order_by("line_number", "-version")
    )

    context = {
        "agreement": agreement,
        "customer": customer,
        "line_items_data": line_items_data,
        "superseded_items": superseded_items,
    }
    if request.htmx:
        return render(
            request,
            "customers/agreement_detail.html#agreement-detail-partial",
            context,
        )
    return render(request, "customers/agreement_detail.html", context)


def sales(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    filter_status = request.GET.get("status", "")
    filter_payment = request.GET.get("payment", "")
    filter_date_from = request.GET.get("date_from", "")
    filter_date_to = request.GET.get("date_to", "")

    sale_list = Sale.objects.select_related("customer").prefetch_related(
        "boxed_sales", "coupled_sales"
    )

    if search_query:
        sale_list = sale_list.filter(
            Q(sale_number__icontains=search_query)
            | Q(customer__full_name__icontains=search_query)
            | Q(customer__customer_number__icontains=search_query)
        )

    if filter_status:
        status_map = {"ACTIVE": "active", "VOIDED": "voided"}
        db_status = status_map.get(filter_status, filter_status.lower())
        sale_list = sale_list.filter(status=db_status)

    if filter_payment:
        payment_map = {
            "from_deposit": "from deposit",
            "transfer": "bank transfer",
            "cash": "cash",
        }
        db_payment = payment_map.get(filter_payment, filter_payment)
        sale_list = sale_list.filter(payment_method=db_payment)

    if filter_date_from:
        sale_list = sale_list.filter(sale_date__date__gte=filter_date_from)

    if filter_date_to:
        sale_list = sale_list.filter(sale_date__date__lte=filter_date_to)

    # Sorting
    sort_field = request.GET.get("sort", "sale_date")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = [
        "sale_date",
        "sale_number",
        "customer__full_name",
        "payment_method",
        "status",
    ]

    if direction == "desc":
        order_by_field = f"-{sort_field}"
    else:
        order_by_field = sort_field

    if sort_field in allowed_sort_fields:
        sale_list = sale_list.order_by(order_by_field)

    paginator = Paginator(sale_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "sales": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
        "filter_status": filter_status,
        "filter_payment": filter_payment,
        "filter_date_from": filter_date_from,
        "filter_date_to": filter_date_to,
    }

    if request.htmx:
        if any(key in request.GET for key in ["q", "status", "payment", "date_from", "date_to", "page"]):
            return render(
                request,
                "customers/sales/sales.html#sales-table-partial",
                context,
            )
        return render(
            request,
            "customers/sales/sales.html#sales-list-partial",
            context,
        )

    return render(request, "customers/sales/sales.html", context)


def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related(
            "customer", "created_by", "agreement"
        ).prefetch_related(
            "boxed_sales__product", "coupled_sales__transformation_item"
        ),
        pk=pk,
    )

    context = {
        "sale": sale,
    }

    if request.htmx:
        return render(
            request,
            "customers/sales/sale_detail.html#sale-detail-partial",
            context,
        )

    return render(request, "customers/sales/sale_detail.html", context)


# def search_customers(request):
#     query = request.GET.get("q", "")
#     customers = []
#     if query:
#         customers = Customer.objects.filter(
#             Q(full_name__icontains=query)
#             | Q(phone__icontains=query)
#             | Q(customer_number__icontains=query)
#         )[:10]
#     return render(
#         request, "partials/search_results_customer.html", {"customers": customers}
#     )


# def search_products(request):
#     query = request.GET.get("q", "")
#     products = []
#     if query:
#         products = Product.objects.filter(
#             Q(modelname__icontains=query)
#             | Q(sku__icontains=query)
#             | Q(brand__name__icontains=query),
#             type_variant=Product.TypeVariant.BOXED,
#         ).select_related("brand")[:10]
#     return render(
#         request, "partials/search_results_product.html", {"products": products}
#     )


# def search_transformation_items(request):
#     query = request.GET.get("q", "")
#     items = []
#     if query:
#         items = TransformationItem.objects.filter(
#             Q(item_number__icontains=query)
#             | Q(engine_number__icontains=query)
#             | Q(chassis_number__icontains=query)
#             | Q(target_product__brand__name__icontains=query)
#             | Q(target_product__modelname__icontains=query),
#             status=TransformationItem.Status.AVAILABLE,
#         ).select_related("target_product")[:10]
#     return render(
#         request, "partials/search_results_transformation_item.html", {"items": items}
#     )


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


def modal_void_sale(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related("customer__deposit_account"), pk=pk
    )

    if request.method == "POST":
        void_reason = request.POST.get("void_reason", "")
        try:
            customer_services.void_sale(pk, void_reason, request.user, request=request)
            messages.success(request, f"Sale {sale.sale_number} voided successfully.")
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "saleDetailChanged"
            return response

        except customer_services.BusinessRuleViolation as e:
            error_msg = str(e)
            return render(
                request,
                "customers/modals/void_sale_modal.html",
                {
                    "sale": sale,
                    "error": error_msg,
                },
            )

    return render(
        request,
        "customers/modals/void_sale_modal.html",
        {
            "sale": sale,
        },
    )
