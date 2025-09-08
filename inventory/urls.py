from django.urls import path
from .views import *


urlpatterns = [
    path("", products, name="products"),
    path("product_detail/<str:pk>/", product_detail, name="product_detail"),
    path("add", manage_products, name="add_product"),
    path("edit/<str:pk>/", manage_products, name="edit_product"),
    path("delete/<str:pk>", delete_product, name="delete_product"),
    path("status_change/<str:pk>", status_change, name="status_change"),
    path("overview/<str:pk>/", overview, name="overview"),
    path("transaction/<str:pk>/", transaction, name="transaction"),
]
