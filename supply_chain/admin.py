from django.contrib import admin
from .models import *
from django.core.exceptions import ValidationError
from django.db import models


class PurchaseInLine(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


class GoodsReceiptInLine(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 0


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "salutation",
        "firstname",
        "lastname",
        "company_name",
        "display_name",
        "email",
        "work_phone",
        "mobile",
        "address",
    )
    search_fields = ("display_name",)


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "supplier",
        "po_number",
        "order_date",
        "delivery_date",
        "delivery_status",
        "payment_status",
        "total_amount",
    )
    search_fields = ("supplier", "po_number", "status")
    inlines = [
        PurchaseInLine,
    ]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_order",
        "product",
        "ordered_quantity",
        "received_quantity",
        "unit_price_at_order",
        "status",
    )
    search_fields = ("purchase_order", "product", "status")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "purchase_order",
        "amount_paid",
        "payment_date",
        "payment_method",
        "trxn_ref",
        "status",
        "remark",
    )
    search_fields = ("purchase_order", "trxn_ref", "status")


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "gr_number",
        "purchase_order",
        "delivery_date",
        "received_by",
        "status",
    )
    search_fields = ("purchase_order", "received_by", "status")
    inlines = [
        GoodsReceiptInLine,
    ]


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(admin.ModelAdmin):
    list_display = (
        "goods_receipt",
        "purchase_order_item",
        "product",
        "received_quantity",
    )
    search_fields = ("goods_receipt", "purchase_order_item", "product", "serial_item")
