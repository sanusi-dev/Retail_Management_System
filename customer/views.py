from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_GET
from render_block import render_block_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.http import HttpResponse
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
    NormalSaleForm,
    AgreementSaleForm,
    BoxedSaleFormSet,
    CoupledSaleFormSet,
)
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


def customers(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    customer_list = Customer.objects.all()
    paginator = Paginator(customer_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"customers": page_obj}

    if request.htmx:
        if request.GET.get("page"):
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
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    customer = get_object_or_404(Customer, pk=pk)
    customer_list = Customer.objects.all().order_by("created_at")
    paginator = Paginator(customer_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "customer": customer,
        "customer_list": page_obj,
    }
    if request.htmx:
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "customers/customer_detail.html",
                "main_content",
                {"customer": customer},
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

    agreements = agreements.order_by("-created_at")

    context = {
        "agreements": agreements,
    }

    return render(request, "customers/partials/purchase_agreements_list.html", context)


@require_GET
def filter_cfa_agreements_partial(request, pk):

    customer = get_object_or_404(Customer, pk=pk)
    agreements = customer.deposit_account.cfa_agreements.all()

    status_filter = request.GET.get("status")
    if status_filter:
        agreements = agreements.filter(status=status_filter)

    agreements = agreements.order_by("-created_at")

    context = {
        "cfas": agreements,
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
    PAGE_SIZE = 20
    page_number = request.GET.get("page", 1)
    customer_pk = request.GET.get("customer")
    transaction_list = Transaction.objects.all()
    if request.GET.get("customer"):
        transaction_list = Transaction.objects.filter(account__customer__pk=customer_pk)
    paginator = Paginator(transaction_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"transactions": page_obj}

    if request.htmx:
        if request.GET.get("page"):
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
            with transaction.atomic():
                txn = form.save(commit=False)
                txn.created_by = request.user
                txn.updated_by = request.user
                txn.save()

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
        with transaction.atomic():
            txn.status = Transaction.Status.VOIDED
            txn.updated_by = request.user
            txn.save()

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

    except ValidationError as e:
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

            return redirect(agreement.account.customer.get_absolute_url)

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

    with transaction.atomic():
        if agreement.can_cancel:
            agreement.status = PurchaseAgreement.Status.CANCELLED
            agreement.save(update_fields=["status"])

            for item in agreement.agreement_line_items.all():
                item.status = PurchaseAgreementLineItem.Status.CANCELLED
                item.save(update_fields=["status"])

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
            with transaction.atomic():
                cfa_agreement = form.save(commit=False)

                if cfa_agreement._state.adding:
                    cfa_agreement.created_by = request.user
                cfa_agreement.updated_by = request.user
                cfa_agreement.save()

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

    with transaction.atomic():
        if agreement.can_cancel:
            agreement.status = CfaAgreement.Status.CANCELLED
            agreement.save(update_fields=["status"])

        toast = render_to_string(
            "partials/toast.html",
            {
                "message": f"Transaction {agreement.cfa_agreement_number} cancelled successfully.",
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
                with transaction.atomic():
                    fulfillment = form.save(commit=False)
                    fulfillment.created_by = request.user
                    fulfillment.updated_by = request.user
                    fulfillment.save()

                return redirect(
                    fulfillment.cfa_agreement.account.customer.get_absolute_url
                )

            except Exception as e:
                error_message = (
                    request,
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
    with transaction.atomic():
        if fulfillment.status == CfaFulfillment.Status.ACTIVE:
            fulfillment.status = CfaFulfillment.Status.VOIDED
            fulfillment.updated_by = request.user
            fulfillment.save()

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


def sales(request):
    PAGE_SIZE = 20
    page_number = request.GET.get("page", 1)
    customer_pk = request.GET.get("customer")
    sale_list = Sale.objects.all()
    if request.GET.get("customer"):
        sale_list = Sale.objects.filter(customer__pk=customer_pk)
    paginator = Paginator(sale_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"sales": page_obj}

    if request.htmx:
        if request.GET.get("page"):
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
    PAGE_SIZE = 10
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
    paginator = Paginator(all_sales, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "sale": sale,
        "sale_list": page_obj,
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


def manage_sales(request):
    pass


# def create_normal_sale(request):
#     if request.method == "POST":
#         form = NormalSaleForm(request.POST)
#         boxed_formset = BoxedSaleFormSet(request.POST, prefix="boxed")
#         coupled_formset = CoupledSaleFormSet(request.POST, prefix="coupled")

#         if form.is_valid() and boxed_formset.is_valid() and coupled_formset.is_valid():
#             try:
#                 with transaction.atomic():
#                     sale = form.save()  # Customer creation happens inside form.save()

#                     # Save Boxed Items
#                     boxed_instances = boxed_formset.save(commit=False)
#                     for item in boxed_instances:
#                         item.sale = sale
#                         item.save()

#                     # Save Coupled Items
#                     coupled_instances = coupled_formset.save(commit=False)
#                     for item in coupled_instances:
#                         item.sale = sale
#                         item.save()

#                 return redirect("sales")
#             except Exception as e:
#                 logging.error(e, exc_info=True)
#     else:
#         form = NormalSaleForm()
#         boxed_formset = BoxedSaleFormSet(prefix="boxed")
#         coupled_formset = CoupledSaleFormSet(prefix="coupled")

#     context = {
#         "form": form,
#         "boxed_formset": boxed_formset,
#         "coupled_formset": coupled_formset,
#         "is_normal_sale": True,
#         "title": "Record Normal Sale",
#     }
#     return render(request, "sales/create_sale.html", context)


# def create_agreement_fulfillment_sale(request, line_item_id):
#     line_item = get_object_or_404(PurchaseAgreementLineItem, pk=line_item_id)

#     # Determine which formset to prefill based on your logic (assuming Boxed for this example)
#     # You might pass a query param ?type=coupled if you want to switch modes
#     sale_type = request.GET.get("type", "boxed")

#     if request.method == "POST":
#         # Pass the line item to the parent form so it knows context
#         form = AgreementSaleForm(request.POST, agreement_line_item=line_item)

#         # Initialize formsets
#         boxed_formset = BoxedSaleFormSet(
#             request.POST, prefix="boxed", form_kwargs={"agreement_line_item": line_item}
#         )
#         coupled_formset = CoupledSaleFormSet(
#             request.POST,
#             prefix="coupled",
#             form_kwargs={"agreement_line_item": line_item},
#         )

#         if form.is_valid():
#             # Special check: Validate FormSets based on expected type
#             valid_boxed = boxed_formset.is_valid()
#             valid_coupled = coupled_formset.is_valid()

#             if valid_boxed and valid_coupled:
#                 try:
#                     with transaction.atomic():
#                         sale = form.save(commit=False)
#                         # Ensure fields that were disabled in UI are forced in backend
#                         sale.customer = line_item.purchase_agreement.account.customer
#                         sale.agreement = line_item.purchase_agreement
#                         sale.payment_method = Sale.PaymentMethod.FROM_DEPOSIT
#                         sale.save()

#                         # Save Boxed Items
#                         boxed_instances = boxed_formset.save(commit=False)
#                         for item in boxed_instances:
#                             item.sale = sale
#                             # Enforce the line item link
#                             item.agreement_line_item = line_item
#                             item.product = line_item.product
#                             item.price = line_item.price_per_unit
#                             item.save()

#                         # Save Coupled Items
#                         coupled_instances = coupled_formset.save(commit=False)
#                         for item in coupled_instances:
#                             item.sale = sale
#                             item.agreement_line_item = line_item
#                             item.price = line_item.price_per_unit
#                             item.save()


#                     return redirect("customer_detail", pk=sale.customer.pk)
#                 except Exception as e:
#                     logging.error(e, exc_info=True)
#             else:
#                 messages.error(request, "Please correct errors in the item list.")
#     else:
#         # GET Request: Pre-fill data
#         form = AgreementSaleForm(agreement_line_item=line_item)

#         # We pre-fill the formset with 1 extra form that has the initial data
#         # form_kwargs passes the line_item down to the ItemForm __init__
#         boxed_formset = BoxedSaleFormSet(
#             prefix="boxed",
#             form_kwargs={"agreement_line_item": line_item},
#             queryset=BoxedSale.objects.none(),
#         )
#         coupled_formset = CoupledSaleFormSet(
#             prefix="coupled",
#             form_kwargs={"agreement_line_item": line_item},
#             queryset=CoupledSale.objects.none(),
#         )

#     context = {
#         "form": form,
#         "boxed_formset": boxed_formset,
#         "coupled_formset": coupled_formset,
#         "line_item": line_item,
#         "is_normal_sale": False,
#         "sale_type": sale_type,  # Use this in template to show/hide relevant formset
#         "title": f"Fulfill: {line_item.product.modelname} - {line_item.purchase_agreement.purchase_agreement_number}",
#     }
#     return render(request, "sales/create_sale.html", context)
