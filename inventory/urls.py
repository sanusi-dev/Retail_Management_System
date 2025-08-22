from django.urls import path
from .views import *


urlpatterns = [
    path("", products, name="products"),
    path("product_detail", product_detail, name="product_detail"),
    path("add", manage_products, name="add_product"),
    path("edit/<str:pk>/", manage_products, name="edit_product"),
    path("delete/<str:pk>", delete_product, name="delete_product"),
]
