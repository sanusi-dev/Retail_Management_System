from django.urls import path
from .views import *


urlpatterns = [
    path('', products, name='products'),
    # path('product_detail', product_detail, name='product_detail'),
    path('add_product', add_product, name='add_product'),
    path('edit_product/<str:pk>/', edit_product, name='edit_product'),
    path('delete_product/<str:pk>', delete_product, name='delete_product'),
]