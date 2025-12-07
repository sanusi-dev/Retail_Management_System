from django.shortcuts import render, redirect, get_object_or_404
from django_htmx.http import replace_url, HttpResponseClientRedirect
from django_htmx.middleware import HtmxDetails
from django.http import HttpResponse
from .models import *
from .forms import *
from django.contrib import messages
from render_block import render_block_to_string
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.db import transaction
from . import services
import logging

logger = logging.getLogger(__name__)


def products(request):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    products_list = Product.objects.select_related("brand").order_by("-created_at")
    paginator = Paginator(products_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {"products": page_obj}

    if request.htmx:
        if request.GET.get("page"):
            product_list = render_block_to_string(
                "inventory/product/product_list.html", "body", context
            )
            return HttpResponse(product_list)

        else:
            product_list = render_block_to_string(
                "inventory/product/product_list.html", "content", context
            )
            return HttpResponse(product_list)

    return render(request, "inventory/product/product_list.html", context)


def manage_products(request, pk=None):
    instance = get_object_or_404(Product, pk=pk) if pk else None

    if request.method == "POST":
        form = ProductForm(request.POST, instance=instance)
        if form.is_valid():
            form = form.save(commit=False)
            form.created_by = request.user
            form.updated_by = request.user
            form.save()
            return redirect("products")

    else:
        form = ProductForm(instance=instance)
    if instance:
        form_acion_url = reverse("edit_product", kwargs={"pk": instance.pk})
    else:
        form_acion_url = reverse("add_product")

    context = {"form": form, "form_action_url": form_acion_url, "instance": instance}
    if request.htmx:
        html = render_block_to_string(
            "inventory/product/form.html", "content", context, request=request
        )
        return HttpResponse(html)
    return render(request, "inventory/product/form.html", context)


def product_detail(request, pk):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    product = get_object_or_404(Product, pk=pk)
    product_list = Product.objects.order_by("created_at")
    paginator = Paginator(product_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "product": product,
        "product_list": page_obj,
    }
    if request.htmx:
        if request.htmx.target == "main_content":
            html = render_block_to_string(
                "inventory/product/product_detail.html",
                "main_content",
                {"product": product},
            )
            return HttpResponse(html)

        elif request.htmx.target == "main_body":
            html = render_block_to_string(
                "inventory/product/product_detail.html", "content", context
            )
            return HttpResponse(html)

        else:
            html = render_block_to_string(
                "inventory/product/product_detail.html", "side_bar_list", context
            )

            return HttpResponse(html)

    else:
        return render(request, "inventory/product/product_detail.html", context)


def product_overview(request, pk):
    product = get_object_or_404(Product, pk=pk)
    context = {"product": product}
    if request.htmx:
        html = render_block_to_string(
            "inventory/product/product_detail.html", "_content", context
        )
        return HttpResponse(html)
    return redirect(product.get_absolute_url)


def product_transaction(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.htmx:
        return render(
            request,
            "inventory/product/partials/_transaction.html",
            {"product": product},
        )
    else:
        return redirect(product.get_absolute_url)


def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "DELETE":
        product.delete()
        products = Product.objects.select_related("brand").filter(
            base_product__isnull=True
        )
        context = {"products": products}

        product_list = render_block_to_string(
            "inventory/product/product_list.html", "content", context
        )

        success_toast = render_to_string(
            "partials/success_toast.html",
            {"message": f"{product.modelname.title()} successfully deleted."},
        )

        full_response = product_list + success_toast
        response = HttpResponse(full_response)
        return replace_url(response, reverse("products"))


def product_status_change(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        if product.status == product.Status.ACTIVE:
            product.status = product.Status.INACTIVE
        else:
            product.status = product.Status.ACTIVE
        product.save()

        context = {"product": product}

        _status_change = render_to_string(
            "inventory/product/partials/_status_change.html", context
        )

        success_toast = render_to_string(
            "partials/success_toast.html",
            {"message": f"The item has been marked as {product.status.title()}."},
        )

        full_response = _status_change + success_toast
        return HttpResponse(full_response)


def inventories(request):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    inventory_list = Inventory.objects.select_related("product").order_by("-quantity")
    paginator = Paginator(inventory_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"inventories": page_obj}

    if request.htmx:
        if request.GET.get("page"):
            inventory_list_html = render_block_to_string(
                "inventory/inventory/inventory.html", "body", context
            )
            return HttpResponse(inventory_list_html)

        else:
            inventory_list_html = render_block_to_string(
                "inventory/inventory/inventory.html", "content", context
            )
            return HttpResponse(inventory_list_html)

    return render(request, "inventory/inventory/inventory.html", context)


def serialized_inventories(request):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    serialized_inventory_list = TransformationItem.objects.select_related(
        "target_product"
    ).order_by("-created_at")
    paginator = Paginator(serialized_inventory_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"serialized_inventories": page_obj}

    if request.htmx:
        if request.GET.get("page"):
            serialized_inventory_list_html = render_block_to_string(
                "inventory/inventory/serialized_inventory.html", "body", context
            )
            return HttpResponse(serialized_inventory_list_html)

        else:
            serialized_inventory_list_html = render_block_to_string(
                "inventory/inventory/serialized_inventory.html", "content", context
            )
            return HttpResponse(serialized_inventory_list_html)

    return render(request, "inventory/inventory/serialized_inventory.html", context)


def inventory_transactions(request):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    inventory_transactions = InventoryTransaction.objects.select_related(
        "inventory"
    ).order_by("-created_at")
    paginator = Paginator(inventory_transactions, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"inventory_transactions": page_obj}

    if request.htmx:
        if request.GET.get("page"):
            return HttpResponse(
                render_block_to_string(
                    "inventory/inventory/inventory_transactions.html",
                    "body",
                    context,
                )
            )

        else:
            return HttpResponse(
                render_block_to_string(
                    "inventory/inventory/inventory_transactions.html",
                    "content",
                    context,
                )
            )

    return render(request, "inventory/inventory/inventory_transactions.html", context)


def transformations(request):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    transformations = Transformation.objects.order_by("-created_at")
    paginator = Paginator(transformations, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {"transformations": page_obj}

    if request.htmx:
        if request.GET.get("page"):
            transformations_html = render_block_to_string(
                "inventory/inventory/inventory_transformations.html", "body", context
            )
            return HttpResponse(transformations_html)

        else:
            transformations_html = render_block_to_string(
                "inventory/inventory/inventory_transformations.html", "content", context
            )
            return HttpResponse(transformations_html)

    return render(
        request, "inventory/inventory/inventory_transformations.html", context
    )


def transformation_detail(request, pk):
    PAGE_SIZE = 50
    page_number = request.GET.get("page", 1)
    transformation = get_object_or_404(
        Transformation.objects.prefetch_related(
            "transformation_items__source_product",
            "transformation_items__target_product",
        ),
        pk=pk,
    )
    transformation_list = Transformation.objects.all()
    paginator = Paginator(transformation_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "transformation": transformation,
        "can_void": services.can_void_transformation(transformation),
        "transformation_list": page_obj,
    }

    if request.htmx:
        if request.htmx.target == "main_content":
            return HttpResponse(
                render_block_to_string(
                    "inventory/inventory/transformation_detail.html",
                    "main_content",
                    context,
                )
            )

        elif request.htmx.target == "main_body":
            return HttpResponse(
                render_block_to_string(
                    "inventory/inventory/transformation_detail.html",
                    "content",
                    context,
                )
            )

        else:
            return HttpResponse(
                render_block_to_string(
                    "inventory/inventory/transformation_detail.html",
                    "side_bar_list",
                    context,
                )
            )

    return render(request, "inventory/inventory/transformation_detail.html", context)


def manage_transformations(request):

    if request.method == "POST":
        form = TransformationForm(request.POST)
        formset = TransformationItemFormset(request.POST, prefix="items")

        if form.is_valid() and formset.is_valid():
            services.process_transformation(form, formset, request)
            return redirect("transformations")

    else:
        form = TransformationForm()
        formset = TransformationItemFormset(
            queryset=TransformationItem.objects.none(), prefix="items"
        )

    context = {
        "transformation_form": form,
        "item_formset": formset,
        "form_action_url": reverse("add_transformation"),
    }

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "inventory/inventory/transformation_form.html", "content", context
            )
        )

    return render(request, "inventory/inventory/transformation_form.html", context)


def manage_transformation_item(request):
    try:
        current_index = int(request.GET.get("index", "0"))
    except ValueError:
        current_index = 0

    formset = TransformationItemFormset(prefix="items")
    empty_form = formset.empty_form
    empty_form.prefix = f"items-{current_index}"

    context = {"form": empty_form}

    return HttpResponse(
        render_block_to_string(
            "inventory/inventory/transformation_form.html", "formset", context
        )
    )


def void_transformation(request, pk):
    transformation = get_object_or_404(
        Transformation.objects.prefetch_related(
            "transformation_items__source_product",
            "transformation_items__target_product",
        ),
        pk=pk,
    )
    if request.method == "POST":
        if services.can_void_transformation(transformation):
            services.void_and_correct(pk)
            message = (
                f"Transformation {transformation.transformation_number} has been voided"
            )
        else:
            message = f"{transformation.transformation_number} can not be voided"

        void = render_block_to_string(
            "inventory/inventory/transformation_detail.html",
            "void",
            {"transformation": transformation},
        )
        toast = render_to_string("partials/success_toast.html", {"message": message})

        return HttpResponse(void + toast)
