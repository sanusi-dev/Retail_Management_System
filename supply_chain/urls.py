from django.urls import path
from .views import *


urlpatterns = [
    path("suppliers/", suppliers, name="suppliers"),
    path("suppliers/add/", manage_supplier, name="add_supplier"),
    path("suppliers/edit/<str:pk>/", manage_supplier, name="edit_supplier"),
    path("suppliers/supplier_detail", supplier_detail, name="supplier_detail"),
    path("suppliers/delete/<str:pk>", delete_supplier, name="delete_supplier"),
    path("po/", purchases, name="purchases"),
    path("po/add/", manage_purchases, name="add_po"),
    path("po/edit/<str:pk>/", manage_purchases, name="edit_po"),
    path("po_detail", po_detail, name="po_detail"),
    path("po/delete/<str:pk>", delete_po, name="delete_po"),
    # +++ NEW URL FOR HTMX +++
    path("htmx/po/add-item/", htmx_add_po_item, name="htmx_add_po_item"),
]
