from django.shortcuts import render, redirect, get_object_or_404
from .models import *
from .forms import *


def products(request):
    products = Product.objects.select_related("brand")
    context = {"products": products}
    return render(request, "inventory/product/product_list.html", context)


def manage_products(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None

    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            return redirect("products")
    else:
        form = ProductForm(instance=product)

    context = {"form": form}
    return render(request, "inventory/product/form.html", context)


def product_detail(request, pk):
    main_product = get_object_or_404(Product, pk=pk)
    side_bar_product = Product.objects.all()

    context = {
        "main_product": main_product,
        "side_bar_product": side_bar_product,
    }
    return render(request, "inventory/product/product_detail.html", context)


def delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == "POST":
        product.delete()
        return redirect("products")


def mark_as_inactive(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.is_active = False
        product.save()
        return redirect('products')


def htmx_get_main_content(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(
        request, "inventory/product/partials/_full_detail.html", {"product": product}
    )
