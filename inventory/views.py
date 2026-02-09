from django.shortcuts import render, redirect, get_object_or_404
from django_htmx.http import replace_url, HttpResponseClientRedirect
from django_htmx.middleware import HtmxDetails
from django.http import HttpResponse
from .models import (
    Product,
    Inventory,
    TransformationItem,
    InventoryTransaction,
    Transformation,
)
from inventory.forms import ProductForm, TransformationForm, TransformationItemFormset
from django.contrib import messages
from render_block import render_block_to_string
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from . import services
import logging
from core.utils import apply_sorting

logger = logging.getLogger(__name__)


def products(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    products_list = (
        Product.objects.select_related("brand")
        .prefetch_related(
            "po_items",
            "transform_to__coupled_sales",
            "boxed_sales",
            "inventory",
        )
        .order_by("-created_at")
    )

    if search_query:
        products_list = products_list.filter(
            Q(modelname__icontains=search_query)
            | Q(brand__name__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = ["created_at", "modelname", "brand__name", "type_variant", "base_product__modelname", "sku", "category"]

    products_list = apply_sorting(products_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(products_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "products": page_obj, 
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET or "sort" in request.GET:
            product_list = render_block_to_string(
                "inventory/product/product_list.html",
                "body",
                context,
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
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    inventory_list = Inventory.objects.select_related("product").order_by("-quantity")

    if search_query:
        inventory_list = inventory_list.filter(
            Q(product__modelname__icontains=search_query)
            | Q(product__brand__name__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "quantity")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = ["quantity", "product__modelname", "product__brand__name", "updated_at"]

    if sort_field not in allowed_sort_fields:
        # Default sort if invalid or missing
        inventory_list = inventory_list.order_by("-quantity")
    else:
        inventory_list = apply_sorting(inventory_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(inventory_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "inventories": page_obj, 
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET:
            inventory_list_html = render_block_to_string(
                "inventory/inventory/inventory.html",
                "body",
                context,
            )
            return HttpResponse(inventory_list_html)

        else:
            inventory_list_html = render_block_to_string(
                "inventory/inventory/inventory.html", "content", context
            )
            return HttpResponse(inventory_list_html)

    return render(request, "inventory/inventory/inventory.html", context)


def serialized_inventories(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")

    serialized_inventory_list = TransformationItem.objects.select_related(
        "target_product"
    ).order_by("-created_at")

    if search_query:
        serialized_inventory_list = serialized_inventory_list.filter(
            Q(item_number__icontains=search_query)
            | Q(engine_number__icontains=search_query)
            | Q(chassis_number__icontains=search_query)
            | Q(target_product__modelname__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = ["created_at", "item_number", "engine_number", "chassis_number", "target_product__modelname", "status"]

    serialized_inventory_list = apply_sorting(serialized_inventory_list, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(serialized_inventory_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "serialized_inventories": page_obj, 
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET or "sort" in request.GET:
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
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    inventory_transactions = InventoryTransaction.objects.select_related(
        "inventory"
    ).order_by("-created_at")

    if search_query:
        inventory_transactions = inventory_transactions.filter(
            Q(inventory__product__modelname__icontains=search_query)
            | Q(transaction_type__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    if sort_field == "quantity":
        sort_field = "quantity_change"
        
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = ["created_at", "reference_number", "transaction_type", "inventory__product__modelname", "quantity_change", "inventory__product__brand__name"]

    inventory_transactions = apply_sorting(inventory_transactions, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(inventory_transactions, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "inventory_transactions": page_obj, 
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET or "sort" in request.GET:
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
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    transformations = Transformation.objects.order_by("-created_at")

    if search_query:
        transformations = transformations.filter(
            Q(transformation_number__icontains=search_query)
        )

    # Sorting
    sort_field = request.GET.get("sort", "created_at")
    direction = request.GET.get("direction", "desc")
    allowed_sort_fields = ["created_at", "transformation_number", "status"]

    transformations = apply_sorting(transformations, sort_field, direction, allowed_sort_fields)

    paginator = Paginator(transformations, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "transformations": page_obj, 
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if "page" in request.GET or "q" in request.GET or "sort" in request.GET:
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
    transformation_list = Transformation.objects.all().order_by("-created_at")

    search_query = request.GET.get("q", "")
    if search_query:
        transformation_list = transformation_list.filter(
            Q(transformation_number__icontains=search_query)
        )

    paginator = Paginator(transformation_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "transformation": transformation,
        "can_void": services.can_void_transformation(transformation),
        "transformation_list": page_obj,
        "search_query": search_query,
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
