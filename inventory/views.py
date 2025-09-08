from django.shortcuts import render, redirect, get_object_or_404
from django_htmx.http import replace_url, HttpResponseClientRedirect
from django_htmx.middleware import HtmxDetails
from django.http import HttpResponse
from .models import *
from .forms import *
from django.contrib import messages
import time
from render_block import render_block_to_string
from django.template.loader import render_to_string
from django.core.paginator import Paginator


def products(request):
    PAGE_SIZE = 15
    page_number = request.GET.get("page", 1)
    products_list = (
        Product.objects.select_related("brand")
        .filter(base_product__isnull=True)
        .order_by("created_at")
    )
    paginator = Paginator(products_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {"products": page_obj}

    if request.htmx:
        # For pagination
        if request.GET.get("page"):
            product_list = render_block_to_string(
                "inventory/product/product_list.html", "table_with_pagination", context
            )
            return HttpResponse(product_list)

        else:
            # For HTMX navigation, render the whole content block
            time.sleep(0.5)
            product_list = render_block_to_string(
                "inventory/product/product_list.html", "content", context
            )
            return HttpResponse(product_list)

    # For a standard full-page load
    return render(request, "inventory/product/product_list.html", context)


def manage_products(request, pk=None):
    instance = get_object_or_404(Product, pk=pk) if pk else None

    if request.method == "POST":
        form = ProductForm(request.POST, instance=instance)
        if form.is_valid():
            form = form.save(commit=False)
            form.created_by = request.user
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
        time.sleep(0.5)
        html = render_block_to_string("inventory/product/form.html", "content", context)
        return HttpResponse(html)
    return render(request, "inventory/product/form.html", context)


def product_detail(request, pk):
    PAGE_SIZE = 17
    page_number = request.GET.get("page", 1)
    product = get_object_or_404(Product, pk=pk)
    product_list = Product.objects.filter(base_product__isnull=True).order_by(
        "created_at"
    )
    paginator = Paginator(product_list, PAGE_SIZE)
    page_obj = paginator.get_page(page_number)

    context = {
        "product": product,
        "product_list": page_obj,
    }
    if request.htmx:
        if request.htmx.target == "main_content":
            time.sleep(0.5)
            html = render_block_to_string(
                "inventory/product/product_detail.html",
                "main_content",
                {"product": product},
            )
            return HttpResponse(html)

        elif request.htmx.target == "main_body":
            time.sleep(0.5)
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


def overview(request, pk):
    product = get_object_or_404(Product, pk=pk)
    context = {"product": product}
    if request.htmx:
        html = render_block_to_string(
            "inventory/product/product_detail.html", "_content", context
        )
        return HttpResponse(html)
    return redirect(product.get_absolute_url)


def transaction(request, pk):
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


def status_change(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        if product.status == product.Status.ACTIVE:
            product.status = product.Status.INACTIVE
        else:
            product.status = product.Status.ACTIVE
        product.save()
        messages.success(
            request, f"The item has been marked as {product.status.title()}."
        )

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
