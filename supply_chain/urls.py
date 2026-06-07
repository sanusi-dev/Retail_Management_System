from django.urls import path
from .views import *

urlpatterns = [
    # =============== SUPPLIER VIEWS ===============
    path("suppliers/", suppliers, name="suppliers"),
    path("suppliers/modal/add/", modal_manage_supplier, name="modal_add_supplier"),
    path("suppliers/modal/<uuid:pk>/", modal_manage_supplier, name="modal_edit_supplier"),
    path("suppliers/delete/<uuid:pk>", delete_supplier, name="delete_supplier"),
    path("supplier_detail/<uuid:pk>/", supplier_detail, name="supplier_detail"),
    # =============== PURCHASE ORDER (PO) VIEWS ===============
    path("po/", purchases, name="purchases"),
    path("po/add/", manage_purchases, name="add_po"),
    path("po/edit/<uuid:pk>/", manage_purchases, name="edit_po"),
    path("po/line_item/add/", po_line_item_add, name="po_line_item_add"),
    path("po/line_item/remove/<int:index>/", po_line_item_remove, name="po_line_item_remove"),
    path("po/delete/<uuid:pk>", delete_po, name="delete_po"),
    path("po_detail/<uuid:pk>", po_detail, name="po_detail"),
    # =============== PAYMENT VIEWS ===============
    path("payment/", payments, name="payments"),
    path("payment_detail/<uuid:pk>", payments_detail, name="payment_detail"),
    path("payments/modal/add/", modal_manage_payment, name="modal_add_payment"),
    path("payments/modal/void/<uuid:pk>/", modal_void_payment, name="modal_void_payment"),
    # =============== GOODS RECEIPT VIEWS ===============
    path("receipts/", good_receipts, name="receipts"),
    path("receipts/add/", manage_receipts, name="add_receipt"),
    path(
        "receipts/receipt_item_form/",
        manage_receipt_item,
        name="receipt_item_form",
    ),
    path("receipts/modal/void/<uuid:pk>/", modal_void_receipt, name="modal_void_receipt"),
    path("receipt_detail/<uuid:pk>", receipt_detail, name="receipt_detail"),
]
