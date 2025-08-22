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


def delete_product(request, pk):
    product = Product.objects.get(pk=pk)

    if request.method == "POST":
        product.delete()
        return redirect("products")


def product_detail(request):
    pass
