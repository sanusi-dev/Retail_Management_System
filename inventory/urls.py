from django.urls import path
from .views import *


urlpatterns = [
    path("", products, name="products"),
    path("product_detail/<str:pk>/", product_detail, name="product_detail"),
    path("add", manage_products, name="add_product"),
    path("edit/<str:pk>/", manage_products, name="edit_product"),
    path("delete/<str:pk>", delete_product, name="delete_product"),
    path("mark_as_inactive/<str:pk>", mark_as_inactive, name="mark_as_inactive"),
    path("get_main_content/<str:pk>", htmx_get_main_content, name="get_main_content"),
]
