from django.shortcuts import render, redirect, get_object_or_404
from django_htmx.http import replace_url
from django.http import HttpResponse
from .models import (
    Product,
    TransformationItem,
    InventoryTransaction,
    Transformation,
    InventoryCostLayer,
)
from .forms import ProductForm, TransformationForm, TransformationItemFormset
from django.contrib import messages
from django.db import transaction
from django.template.loader import render_to_string
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Q, Count
from django.urls import reverse
from . import services
import logging
from core.utils import apply_sorting
from decimal import Decimal
import urllib.parse
from django.http import QueryDict

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
    allowed_sort_fields = [
        "created_at",
        "modelname",
        "brand__name",
        "type_variant",
        "base_product__modelname",
        "sku",
        "category",
    ]

    products_list = apply_sorting(
        products_list, sort_field, direction, allowed_sort_fields
    )

    paginator = Paginator(products_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "products": page_obj,
        "search_query": search_query,
        "sort_field": sort_field,
        "direction": direction,
    }

    if request.htmx:
        if any(key in request.GET for key in ["page", "q", "sort", "direction"]):
            return render(
                request,
                "inventory/product/product_list.html#product-table-partial",
                context,
            )
        return render(
            request,
            "inventory/product/product_list.html#product-list-partial",
            context,
        )

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
        return render(
            request,
            "inventory/product/form.html#product-form-partial",
            context,
        )
    return render(request, "inventory/product/form.html", context)


def modal_manage_product(request, pk=None):
    instance = get_object_or_404(Product, pk=pk) if pk else None

    if request.method == "POST":
        form = ProductForm(request.POST, instance=instance)
        if form.is_valid():
            product = form.save(commit=False)
            if not instance:
                product.created_by = request.user
            product.updated_by = request.user
            product.save()
            action = "updated" if instance else "created"
            messages.success(
                request,
                f"Product {product.modelname} ({product.sku}) {action}.",
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "productChanged"
            return response
    else:
        form = ProductForm(instance=instance)

    return render(
        request,
        "inventory/product/modals/manage_product_modal.html",
        {"form": form, "instance": instance},
    )


def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "DELETE":
        product.delete()
        products = Product.objects.select_related("brand").filter(
            base_product__isnull=True
        )
        context = {"products": products}

        resp = render(
            request,
            "inventory/product/product_list.html#product-list-partial",
            context,
        )

        success_toast = render_to_string(
            "partials/success_toast.html",
            {"message": f"{product.modelname.title()} successfully deleted."},
        )

        resp.content = resp.content + success_toast.encode()
        response = resp
        return replace_url(response, reverse("products"))

    return HttpResponse(status=405)


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

    return HttpResponse(status=405)


def inventories(request):
    PAGE_SIZE = 50

    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    category_filter = request.GET.get("category", "")
    stock_filter = request.GET.get("stock", "")
    sort_field = request.GET.get("sort", "total_value")
    direction = request.GET.get("direction", "desc")

    FILTER_KEYS = {"page", "q", "category", "stock", "sort"}

    # --- Base queryset ---
    base_products = (
        Product.objects.filter(base_product__isnull=True)
        .select_related("brand", "inventory")
        .prefetch_related("variants__transform_to")
        .order_by("modelname")
    )

    if search_query:
        base_products = base_products.filter(
            Q(modelname__icontains=search_query)
            | Q(brand__name__icontains=search_query)
            | Q(sku__icontains=search_query)
        )

    if category_filter:
        base_products = base_products.filter(category=category_filter)

    # --- Bulk-fetch latest cost layers (SQLite-compatible) ---
    latest_layer_subquery = (
        InventoryCostLayer.objects.filter(
            product=OuterRef("pk"),
            remaining_quantity__gt=0,
            is_voided=False,
        )
        .order_by("-created_at")
        .values("cost_layer_id")[:1]
    )

    latest_layer_ids = base_products.annotate(
        latest_layer_id=Subquery(latest_layer_subquery)
    ).values_list("latest_layer_id", flat=True)

    latest_layers = {
        layer.product_id: layer
        for layer in InventoryCostLayer.objects.filter(
            cost_layer_id__in=latest_layer_ids
        )
    }

    # --- Build product data in Python ---
    products_with_data = []
    low_stock_items = []
    total_inventory_value = Decimal("0.00")

    for product in base_products:
        # Boxed qty
        try:
            boxed_qty = product.inventory.quantity
        except Product.inventory.RelatedObjectDoesNotExist:
            boxed_qty = 0

        # Boxed unit cost: latest cost layer → WAC → zero
        latest_layer = latest_layers.get(product.product_id)
        if latest_layer:
            boxed_unit_cost = latest_layer.unit_cost
        elif hasattr(product, "inventory"):
            boxed_unit_cost = product.inventory.weighted_average_cost
        else:
            boxed_unit_cost = Decimal("0.00")

        boxed_value = Decimal(str(boxed_qty)) * boxed_unit_cost

        # Coupled variant data
        coupled_variant = next(
            (
                v
                for v in product.variants.all()
                if v.type_variant == Product.TypeVariant.COUPLED
            ),
            None,
        )
        coupled_count = 0
        coupled_available = 0
        coupled_unit_cost = Decimal("0.00")
        coupled_value = Decimal("0.00")

        if coupled_variant:
            active_items = [
                ti
                for ti in coupled_variant.transform_to.all()
                if ti.status != TransformationItem.Status.VOIDED
            ]
            coupled_count = len(active_items)
            coupled_available = sum(
                1
                for ti in active_items
                if ti.status == TransformationItem.Status.AVAILABLE
            )
            latest_ti = max(
                active_items,
                key=lambda ti: ti.created_at,
                default=None,
            )
            coupled_unit_cost = (
                latest_ti.unit_cost_at_transformation
                if latest_ti
                else (coupled_variant.assembly_cost or Decimal("0.00"))
            )
            coupled_value = Decimal(str(coupled_count)) * coupled_unit_cost

        total_value = boxed_value + coupled_value
        total_inventory_value += total_value

        # Stock status
        match boxed_qty:
            case 0:
                stock_status = "out"
                low_stock_items.append(
                    {
                        "product": product,
                        "boxed_qty": boxed_qty,
                        "reason": "Out of stock",
                    }
                )
            case qty if qty <= 2:
                stock_status = "low"
                low_stock_items.append(
                    {
                        "product": product,
                        "boxed_qty": boxed_qty,
                        "reason": "Low stock",
                    }
                )
            case _:
                stock_status = "ok"

        # Stock filter
        match stock_filter:
            case "in_stock" if boxed_qty == 0 and coupled_available == 0:
                continue
            case "low_stock" if stock_status != "low":
                continue
            case "out_of_stock" if stock_status != "out":
                continue

        products_with_data.append(
            {
                "product": product,
                "boxed_qty": boxed_qty,
                "boxed_unit_cost": boxed_unit_cost,
                "boxed_value": boxed_value,
                "coupled_variant": coupled_variant,
                "coupled_count": coupled_count,
                "coupled_available": coupled_available,
                "coupled_unit_cost": coupled_unit_cost,
                "coupled_value": coupled_value,
                "total_value": total_value,
            }
        )

    # --- Sorting ---
    sort_key_map = {
        "modelname": lambda x: x["product"].modelname.lower(),
        "boxed_qty": lambda x: x["boxed_qty"],
        "coupled_count": lambda x: x["coupled_count"],
        "total_value": lambda x: x["total_value"],
    }

    if sort_field in sort_key_map:
        products_with_data.sort(
            key=sort_key_map[sort_field],
            reverse=(direction == "desc"),
        )

    # --- Pagination ---
    paginator = Paginator(products_with_data, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "products": page_obj,
        "search_query": search_query,
        "category_filter": category_filter,
        "stock_filter": stock_filter,
        "sort_field": sort_field,
        "direction": direction,
        "low_stock_items": low_stock_items,
        "total_inventory_value": total_inventory_value,
        "category_choices": Product.Category.choices,
    }

    # --- HTMX rendering ---
    if request.htmx:
        match any(key in request.GET for key in FILTER_KEYS):
            case True:
                return render(
                    request,
                    "inventory/inventory/inventory.html#inventory-table-partial",
                    context,
                )
            case False:
                return render(
                    request,
                    "inventory/inventory/inventory.html#inventory-list-partial",
                    context,
                )

    return render(request, "inventory/inventory/inventory.html", context)


def product_detail(request, pk):
    """Detail view for a base product showing boxed + coupled breakdown."""
    product = get_object_or_404(
        Product.objects.select_related("brand", "inventory").prefetch_related(
            "variants"
        ),
        pk=pk,
        base_product__isnull=True,
    )

    # Boxed data
    boxed_qty = product.inventory.quantity if hasattr(product, "inventory") else 0
    boxed_wac = (
        product.inventory.weighted_average_cost
        if hasattr(product, "inventory")
        else Decimal("0.00")
    )
    boxed_value = Decimal(str(boxed_qty)) * boxed_wac

    # Coupled data
    coupled_variant = product.variants.filter(
        type_variant=Product.TypeVariant.COUPLED
    ).first()

    coupled_count = 0
    coupled_available = 0
    coupled_sold = 0
    coupled_reserved = 0
    coupled_assembly_cost = Decimal("0.00")
    coupled_value = Decimal("0.00")
    serialized_items = []

    if coupled_variant:
        all_items = (
            coupled_variant.transform_to.exclude(
                status=TransformationItem.Status.VOIDED
            )
            .select_related("transformation")
            .order_by("-created_at")
        )
        serialized_items = list(all_items)
        coupled_count = len(serialized_items)
        coupled_available = sum(
            1
            for i in serialized_items
            if i.status == TransformationItem.Status.AVAILABLE
        )
        coupled_sold = sum(
            1 for i in serialized_items if i.status == TransformationItem.Status.SOLD
        )
        coupled_reserved = sum(
            1
            for i in serialized_items
            if i.status == TransformationItem.Status.RESERVED
        )
        coupled_assembly_cost = coupled_variant.assembly_cost or Decimal("0.00")
        coupled_value = Decimal(str(coupled_count)) * coupled_assembly_cost

    total_value = boxed_value + coupled_value

    # Tab data
    tab = request.GET.get("tab", "units")

    # Stock history: inventory transactions for boxed product + transformation items
    stock_history = []
    if hasattr(product, "inventory"):
        stock_history = list(
            InventoryTransaction.objects.filter(inventory=product.inventory)
            .select_related("inventory")
            .order_by("-created_at")[:100]
        )

    # Cost layers
    cost_layers_qs = (
        InventoryCostLayer.objects.filter(product=product)
        .select_related("goods_receipt_item__goods_receipt")
        .prefetch_related("sale_consumptions", "transformation_consumptions")
        .order_by("created_at")
    )

    cost_layers = []
    for layer in cost_layers_qs:
        consumed = layer.quantity - layer.remaining_quantity
        value = layer.remaining_quantity * layer.unit_cost
        cost_layers.append(
            {
                "layer": layer,
                "consumed": consumed,
                "value": value,
            }
        )

    # Sales data
    from customer.models import BoxedSale, CoupledSale, Sale

    boxed_sales = (
        BoxedSale.objects.filter(product=product, sale__status=Sale.Status.ACTIVE)
        .select_related("sale", "sale__customer")
        .order_by("-sale__sale_date")[:100]
    )

    coupled_sales = []
    if coupled_variant:
        coupled_sales = (
            CoupledSale.objects.filter(
                transformation_item__target_product=coupled_variant,
                sale__status=Sale.Status.ACTIVE,
            )
            .select_related("sale", "sale__customer", "transformation_item")
            .order_by("-sale__sale_date")[:100]
        )

    # Calculate average sale price across both variants
    avg_sale_price = Decimal("0.00")
    total_revenue = Decimal("0.00")
    total_units_sold = 0

    for bs in boxed_sales:
        total_revenue += bs.price * bs.quantity
        total_units_sold += bs.quantity

    for cs in coupled_sales:
        total_revenue += cs.price
        total_units_sold += 1

    if total_units_sold > 0:
        avg_sale_price = total_revenue / total_units_sold

    # Calculate total profit from coupled sales
    coupled_profit = Decimal("0.00")
    for cs in coupled_sales:
        cost = cs.transformation_item.unit_cost_at_transformation or Decimal("0.00")
        coupled_profit += cs.price - cost

    # Calculate total profit from boxed sales
    boxed_profit = Decimal("0.00")
    for bs in boxed_sales:
        if bs.cost_basis is not None:
            boxed_profit += (bs.price * bs.quantity) - bs.cost_basis
        else:
            wac = bs.product.inventory.weighted_average_cost or Decimal("0.00")
            boxed_profit += (bs.price - wac) * bs.quantity

    total_profit = coupled_profit + boxed_profit

    context = {
        "product": product,
        "coupled_variant": coupled_variant,
        "tab": tab,
        # Boxed
        "boxed_qty": boxed_qty,
        "boxed_wac": boxed_wac,
        "boxed_value": boxed_value,
        # Coupled
        "coupled_count": coupled_count,
        "coupled_available": coupled_available,
        "coupled_sold": coupled_sold,
        "coupled_reserved": coupled_reserved,
        "coupled_assembly_cost": coupled_assembly_cost,
        "coupled_value": coupled_value,
        # Totals
        "total_value": total_value,
        "avg_sale_price": avg_sale_price,
        "total_units_sold": total_units_sold,
        "coupled_profit": coupled_profit,
        "boxed_profit": boxed_profit,
        "total_profit": total_profit,
        # Tab data
        "serialized_items": serialized_items,
        "stock_history": stock_history,
        "cost_layers": cost_layers,
        "boxed_sales": boxed_sales,
        "coupled_sales": coupled_sales,
    }

    if request.htmx:
        if request.htmx.target == "tab_area":
            return render(
                request,
                "inventory/product/partials/tab_area_partial.html",
                context,
            )
        return render(
            request,
            "inventory/product/product_detail.html#product-detail-partial",
            context,
        )

    return render(request, "inventory/product/product_detail.html", context)


def transformations(request):
    PAGE_SIZE = 100
    page_number = request.GET.get("page", 1)
    search_query = request.GET.get("q", "")
    status_filter = request.GET.get("status", "")
    transformations = Transformation.objects.annotate(
        total_qty=Count("transformation_items")
    ).order_by("-created_at")

    if search_query:
        transformations = transformations.filter(
            Q(transformation_number__icontains=search_query)
        )

    if status_filter:
        transformations = transformations.filter(status=status_filter)

    paginator = Paginator(transformations, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)
    context = {
        "transformations": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
    }

    if request.htmx:
        match any(key in request.GET for key in ["page", "q", "status"]):
            case True:
                return render(
                    request,
                    "inventory/inventory/inventory_transformations.html#transformation-table-partial",
                    context,
                )
            case False:
                return render(
                    request,
                    "inventory/inventory/inventory_transformations.html#transformation-list-partial",
                    context,
                )

    return render(
        request, "inventory/inventory/inventory_transformations.html", context
    )


def transformation_detail(request, pk):
    transformation = get_object_or_404(
        Transformation.objects.prefetch_related(
            "transformation_items__source_product",
            "transformation_items__target_product",
        ),
        pk=pk,
    )

    context = {
        "transformation": transformation,
        "can_void": services.can_void_transformation(transformation),
    }

    if request.htmx:
        return render(
            request,
            "inventory/inventory/transformation_detail.html#transformation-detail-partial",
            context,
        )

    return render(request, "inventory/inventory/transformation_detail.html", context)


def manage_transformations(request):

    if request.method == "POST":
        form = TransformationForm(request.POST)
        formset = TransformationItemFormset(request.POST, prefix="items")

        if form.is_valid() and formset.is_valid():
            transformation = services.process_transformation(form, formset, request)
            messages.success(
                request,
                f"Transformation {transformation.transformation_number} saved successfully.",
            )
            return redirect("transformation_detail", pk=transformation.pk)

    else:
        form = TransformationForm()
        formset = TransformationItemFormset(
            queryset=TransformationItem.objects.none(), prefix="items"
        )

    context = {
        "transformation_form": form,
        "formset": formset,
    }

    if request.htmx:
        return render(
            request,
            "inventory/inventory/transformation_form.html#transformation-form-partial",
            context,
        )

    return render(request, "inventory/inventory/transformation_form.html", context)


def transformation_item_add(request):
    post_data = request.POST.copy()
    total_forms = int(post_data.get("items-TOTAL_FORMS", 0))

    post_data[f"items-{total_forms}-source_product"] = ""
    post_data[f"items-{total_forms}-engine_number"] = ""
    post_data[f"items-{total_forms}-chassis_number"] = ""
    post_data["items-TOTAL_FORMS"] = total_forms + 1

    formset = TransformationItemFormset(post_data, prefix="items")

    return render(
        request,
        "inventory/inventory/transformation_form.html#transformation-formset-partial",
        {"formset": formset},
    )


def transformation_item_remove(request, index):
    post_data = request.POST.copy()
    total_forms = int(post_data.get("items-TOTAL_FORMS", 0))

    line_fields = ["id", "source_product", "engine_number", "chassis_number", "DELETE"]
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

    formset = TransformationItemFormset(rebuilt, prefix="items")

    return render(
        request,
        "inventory/inventory/transformation_form.html#transformation-formset-partial",
        {"formset": formset},
    )


def modal_void_transformation(request, pk):
    transformation = get_object_or_404(
        Transformation.objects.prefetch_related(
            "transformation_items__source_product",
            "transformation_items__target_product",
        ),
        pk=pk,
    )

    if request.method == "POST":
        void_reason = request.POST.get("void_reason", "")
        try:
            services.void_transformation(pk, request.user, request=request)
            messages.success(
                request,
                f"Transformation {transformation.transformation_number} voided successfully.",
            )
            response = HttpResponse(status=204)
            response["HX-Trigger"] = "transformationDetailChanged"
            return response
        except services.BusinessRuleViolation as e:
            return render(
                request,
                "inventory/inventory/modals/void_transformation_modal.html",
                {
                    "transformation": transformation,
                    "error": str(e),
                },
            )

    return render(
        request,
        "inventory/inventory/modals/void_transformation_modal.html",
        {"transformation": transformation},
    )
