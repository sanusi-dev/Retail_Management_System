from django.urls import path
from .views import *

urlpatterns = [
    path("", customers, name="customers"),
    path("customer_detail/<uuid:pk>", customer_detail, name="customer_detail"),
    path("add_customer", manage_customers, name="add_customer"),
    path("edit_customer/<uuid:pk>", manage_customers, name="edit_customer"),
    path("transactions", customer_transactions, name="customer_transactions"),
    path("add_transaction", manage_transactions, name="add_transaction"),
    path(
        "void_transaction/<uuid:pk>/",
        void_transaction,
        name="void_transaction",
    ),
    path("sales", sales, name="sales"),
    path("sale_detail/<uuid:pk>/", sale_detail, name="sale_detail"),
    path("record_sale", record_sale, name="record_sale"),
    path("void_sale/<uuid:pk>/", void_sale, name="void_sale"),
    path("search/customers/", search_customers, name="search_customers"),
    path("search/products/", search_products, name="search_products"),
    path(
        "search/transformation_items/",
        search_transformation_items,
        name="search_transformation_items",
    ),
    path(
        "ajax/load-customer-agreements/",
        load_customer_agreements,
        name="ajax_load_customer_agreements",
    ),
    path(
        "ajax/load-agreement-line-items/",
        load_agreement_line_items,
        name="ajax_load_agreement_line_items",
    ),
    path(
        "add_purchase_agreement",
        manage_purchase_agreements,
        name="add_purchase_agreement",
    ),
    path(
        "edit_purchase_agreement/<uuid:pk>/",
        manage_purchase_agreements,
        name="edit_purchase_agreement",
    ),
    path(
        "add_purchase_agreement_line_item",
        manage_purchase_agreement_line_item,
        name="add_purchase_agreement_line_item",
    ),
    path(
        "cancel_purchase_agreement/<uuid:pk>/",
        cancel_purchase_agreement,
        name="cancel_purchase_agreement",
    ),
    path(
        "add_cfa_agreement",
        manage_cfa_agreements,
        name="add_cfa_agreement",
    ),
    path(
        "edit_cfa_agreement/<uuid:pk>",
        manage_cfa_agreements,
        name="edit_cfa_agreement",
    ),
    path(
        "cancel_cfa_agreement/<uuid:pk>",
        cancel_cfa_agreement,
        name="cancel_cfa_agreement",
    ),
    path(
        "add_cfa_fulfillment",
        manage_cfa_fulfillments,
        name="add_cfa_fulfillment",
    ),
    path(
        "void_cfa_fulfillment/<uuid:pk>",
        void_cfa_fulfillment,
        name="void_cfa_fulfillment",
    ),
    path(
        "modal/deposit/<uuid:pk>",
        modal_deposit,
        name="modal_deposit",
    ),
    path(
        "modal/void_transaction/<uuid:pk>",
        modal_void_transaction,
        name="modal_void_transaction",
    ),
    path(
        "modal/cfa_fulfillment/<uuid:pk>",
        modal_cfa_fulfillment,
        name="modal_cfa_fulfillment",
    ),
    path(
        "modal/void_cfa_fulfillment/<uuid:pk>",
        modal_void_cfa_fulfillment,
        name="modal_void_cfa_fulfillment",
    ),
    path(
        "modal/withdrawal/<uuid:pk>",
        modal_withdrawal,
        name="modal_withdrawal",
    ),
    path(
        "modal/cfa_agreement/<uuid:pk>",
        modal_cfa_agreement,
        name="modal_cfa_agreement",
    ),
    path(
        "modal/cfa_agreement/<uuid:pk>/edit",
        modal_cfa_agreement_edit,
        name="modal_cfa_agreement_edit",
    ),
    path(
        "modal/cancel_cfa_agreement/<uuid:pk>",
        modal_cancel_cfa_agreement,
        name="modal_cancel_cfa_agreement",
    ),
]
