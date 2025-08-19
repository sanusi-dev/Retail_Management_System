from django.shortcuts import render, redirect
from django.db import IntegrityError
from .models import*
from .forms import*


def products(request):
    products = Product.objects.select_related()
    context = {'products': products}
    return render(request, 'inventory/product_list.html', context)


def add_product(request):

    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('products')
    else:
        form = ProductForm()

    context = {
        'form': form
    }
    return render(request, 'inventory/form.html', context)


def edit_product(request, pk):
    product = Product.objects.get(pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
                form.save()
                return redirect('products')
    else:
        form = ProductForm(instance=product)

    context = {
        'form': form
    }
    return render(request, 'inventory/form.html', context)

def delete_product(request, pk):
    product = Product.objects.get(pk=pk)

    if request.method == 'POST':
        product.delete()
        return redirect('products')
