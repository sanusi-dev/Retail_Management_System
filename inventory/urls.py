from django.urls import path
from .views import *


urlpatterns = [
    path("products/", products, name="products"),
    path("product_detail/<uuid:pk>/", product_detail, name="product_detail"),
    path("products/add", manage_products, name="add_product"),
    path("products/edit/<uuid:pk>/", manage_products, name="edit_product"),
    path("products/delete/<uuid:pk>/", delete_product, name="delete_product"),
    path(
        "products/product_status_change/<uuid:pk>/",
        product_status_change,
        name="product_status_change",
    ),
    path("products/overview/<uuid:pk>/", product_overview, name="product_overview"),
    path(
        "products/transaction/<uuid:pk>/",
        product_transaction,
        name="product_transaction",
    ),
    path("inventories/", inventories, name="inventories"),
    path(
        "serialized_inventories/", serialized_inventories, name="serialized_inventories"
    ),
    path(
        "inventory_transactions/", inventory_transactions, name="inventory_transactions"
    ),
    path("transformations/", transformations, name="transformations"),
    path("transformations/add/", manage_transformations, name="add_transformation"),
    path("transformations/item_form/", manage_transformation_item, name="item_form"),
    path(
        "transformations/void/<uuid:pk>",
        void_transformation,
        name="void_transformation",
    ),
    path(
        "transformation_detail/<uuid:pk>",
        transformation_detail,
        name="transformation_detail",
    ),
]
