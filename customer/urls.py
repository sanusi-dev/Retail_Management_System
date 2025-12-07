from django.urls import path
from .views import *


urlpatterns = [
    path("", customers, name="customers"),
    path("customer_detail/<uuid:pk>", customer_detail, name="customer_detail"),
    path(
        "filter_agreements_partial/<uuid:pk>",
        filter_agreements_partial,
        name="filter_agreements_partial",
    ),
    path(
        "filter_cfa_agreements_partial/<uuid:pk>",
        filter_cfa_agreements_partial,
        name="filter_cfa_agreements_partial",
    ),
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
    path("add_sale", manage_sales, name="add_sale"),
    # path("void_sale/<uuid:pk>/", void_sale, name="void_sale"),
    # path("purchase_agreements", purchase_agreements, name="purchase_agreements"),
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
    # path("cfa_fulfillments", cfa_fulfillments, name="cfa_fulfillments"),
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
]
