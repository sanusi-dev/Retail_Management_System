from django.urls import path
from .views import *

urlpatterns = [
    # =============== SUPPLIER VIEWS ===============
    path("suppliers/", suppliers, name="suppliers"),
    path("suppliers/add/", manage_supplier, name="add_supplier"),
    path("suppliers/edit/<uuid:pk>/", manage_supplier, name="edit_supplier"),
    path("suppliers/delete/<uuid:pk>", delete_supplier, name="delete_supplier"),
    path(
        "suppliers/supplier_detail/<uuid:pk>", supplier_detail, name="supplier_detail"
    ),
    path("suppliers/overview/<uuid:pk>/", supplier_overview, name="overview"),
    path("suppliers/transaction/<uuid:pk>/", supplier_transaction, name="transaction"),
    # =============== PURCHASE ORDER (PO) VIEWS ===============
    path("po/", purchases, name="purchases"),
    path("po/add/", manage_purchases, name="add_po"),
    path("po/edit/<uuid:pk>/", manage_purchases, name="edit_po"),
    path("po/po_item_form/", manage_po_item, name="po_item_form"),
    path("po/delete/<uuid:pk>", delete_po, name="delete_po"),
    path("po_detail/<uuid:pk>", po_detail, name="po_detail"),
    # =============== PAYMENT VIEWS ===============
    path("payment/", payments, name="payments"),
    path("payment/add/", manage_payments, name="add_payment"),
    path("payment/void/<uuid:pk>", payments_void, name="void_payment"),
    path("payment_detail/<uuid:pk>", payments_detail, name="payment_detail"),
    # =============== GOODS RECEIPT VIEWS ===============
    path("receipts/", good_receipts, name="receipts"),
    path("receipts/add/", manage_receipts, name="add_receipt"),
    path(
        "receipts/receipt_item_form/",
        manage_receipt_item,
        name="receipt_item_form",
    ),
    path("receipts/void/<uuid:pk>", void_receipt, name="void_receipt"),
    path("receipt_detail/<uuid:pk>", receipt_detail, name="receipt_detail"),
]
