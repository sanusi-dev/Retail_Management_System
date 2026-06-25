from django.urls import path
from .views import *

urlpatterns = [
    path("", customers, name="customers"),
    path("customer_detail/<uuid:pk>", customer_detail, name="customer_detail"),
    path("modal/new_customer", modal_new_customer, name="modal_new_customer"),
    path("transactions", customer_transactions, name="customer_transactions"),
    path("sales", sales, name="sales"),
    path("sale_detail/<uuid:pk>/", sale_detail, name="sale_detail"),
    path("sales/create-sale/", create_normal_sale, name="create_normal_sale"),
    path(
        "sales/normal/boxed-add/",
        normal_sale_boxed_add,
        name="normal_sale_boxed_add",
    ),
    path(
        "sales/normal/boxed-remove/<int:index>/",
        normal_sale_boxed_remove,
        name="normal_sale_boxed_remove",
    ),
    path(
        "sales/normal/coupled-add/",
        normal_sale_coupled_add,
        name="normal_sale_coupled_add",
    ),
    path(
        "sales/normal/coupled-remove/<int:index>/",
        normal_sale_coupled_remove,
        name="normal_sale_coupled_remove",
    ),
    path(
        "sales/normal/search-customers/",
        search_customers_for_sale,
        name="search_customers_for_sale",
    ),
    path(
        "ajax/customer-select/",
        ajax_customer_select,
        name="ajax_customer_select",
    ),
    path(
        "fulfill-agreement/<uuid:customer_id>/<uuid:agreement_id>/",
        fulfill_agreement,
        name="fulfill_agreement",
    ),
    path("modal/void_sale/<uuid:pk>/", modal_void_sale, name="modal_void_sale"),
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
        "purchase_agreement/line_item/add",
        agreement_line_item_add,
        name="agreement_line_item_add",
    ),
    path(
        "purchase_agreement/line_item/remove/<int:index>",
        agreement_line_item_remove,
        name="agreement_line_item_remove",
    ),
    path(
        "modal/cancel_purchase_agreement/<uuid:pk>/",
        modal_cancel_purchase_agreement,
        name="modal_cancel_purchase_agreement",
    ),
    path(
        "modal/amend_line_item/<uuid:pk>/",
        modal_amend_line_item,
        name="modal_amend_line_item",
    ),
    path(
        "agreement_detail/<uuid:pk>/",
        agreement_detail,
        name="agreement_detail",
    ),
    path(
        "modal/deposit/<uuid:pk>/",
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
        "modal/withdrawal/<uuid:pk>/",
        modal_withdrawal,
        name="modal_withdrawal",
    ),
    path(
        "modal/cfa_agreement/<uuid:pk>/",
        modal_cfa_agreement,
        name="modal_cfa_agreement",
    ),
    path(
        "modal/cfa_agreement/<uuid:pk>/edit/",
        modal_cfa_agreement_edit,
        name="modal_cfa_agreement_edit",
    ),
    path(
        "modal/cancel_cfa_agreement/<uuid:pk>/",
        modal_cancel_cfa_agreement,
        name="modal_cancel_cfa_agreement",
    ),
]
