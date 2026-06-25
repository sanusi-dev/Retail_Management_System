from django.urls import path
from .views import *


urlpatterns = [
    path("products/", products, name="products"),
    path("products/modal/add/", modal_manage_product, name="modal_add_product"),
    path("products/modal/<uuid:pk>/", modal_manage_product, name="modal_edit_product"),
    path("products/add", manage_products, name="add_product"),
    path("products/edit/<uuid:pk>/", manage_products, name="edit_product"),
    path("products/delete/<uuid:pk>/", delete_product, name="delete_product"),
    path(
        "products/product_status_change/<uuid:pk>/",
        product_status_change,
        name="product_status_change",
    ),
    path("products/<uuid:pk>/", product_detail, name="product_detail"),
    path("inventories/", inventories, name="inventories"),
    
    path("transformations/", transformations, name="transformations"),
    path("transformations/add/", manage_transformations, name="add_transformation"),
    path("transformations/item/add/", transformation_item_add, name="transformation_item_add"),
    path("transformations/item/remove/<int:index>/", transformation_item_remove, name="transformation_item_remove"),

    path(
        "transformations/modal/void/<uuid:pk>/",
        modal_void_transformation,
        name="modal_void_transformation",
    ),
    path(
        "transformation_detail/<uuid:pk>/",
        transformation_detail,
        name="transformation_detail",
    ),
]
