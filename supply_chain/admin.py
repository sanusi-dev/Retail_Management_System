from django.contrib import admin
from django.db.models import Sum, F
from django.utils.html import format_html
from .models import (
    Supplier,
    PurchaseOrder,
    PurchaseOrderItem,
    Payment,
    GoodsReceipt,
    GoodsReceiptItem,
)

# --- Mixins ---


class AuditAdminMixin:
    """
    Mixin to handle standard audit fields and user tracking.
    """

    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.created_by = request.user
            instance.updated_by = request.user
            instance.save()
        formset.save_m2m()


# --- Inlines ---


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    fields = [
        "product",
        "ordered_quantity",
        "unit_price_at_order",
        "total_price_display",
        "status",
    ]
    readonly_fields = ["total_price_display", "status"]
    autocomplete_fields = ["product"]
    extra = 1

    def total_price_display(self, obj):
        return f"{obj.total_price:,.2f}"

    total_price_display.short_description = "Total"


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    fields = [
        "product",
        "purchase_order_item",
        "received_quantity",
        "unit_cost_at_receipt",
        "allocated_delivery_cost_per_unit",
    ]
    autocomplete_fields = ["product", "purchase_order_item"]
    extra = 0

    # Preventing edits to receipt items is usually safer for stock integrity
    def has_change_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    fields = ["amount_paid", "payment_method", "payment_date", "trxn_ref", "status"]
    readonly_fields = [
        "trxn_ref",
        "payment_date",
        "amount_paid",
        "payment_method",
        "status",
    ]
    extra = 0
    can_delete = False
    verbose_name = "Related Payment"
    verbose_name_plural = "Payment History"

    def has_add_permission(self, request, obj):
        return False


# --- Admin Registration ---


@admin.register(Supplier)
class SupplierAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "company_name",
        "full_name",
        "phone_and_address",
        "status",
        "undelivered_value",
    ]
    list_filter = ["status"]

    search_fields = ["company_name", "full_name", "phone", "address"]

    readonly_fields = ["supplier_id"] + AuditAdminMixin.readonly_fields

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "supplier_id",
                    "company_name",
                    "full_name",
                )
            },
        ),
        (
            "Contact Details",
            {"fields": ("phone", "address")},
        ),
        ("Status", {"fields": ("status",)}),
        (
            "Audit",
            {"fields": AuditAdminMixin.readonly_fields, "classes": ("collapse",)},
        ),
    )

    def phone_and_address(self, obj):
        info = f"Phone: {obj.phone or 'N/A'}"
        if obj.address:
            short_address = (
                obj.address[:30] + "..." if len(obj.address) > 30 else obj.address
            )
            info += format_html(f"<br>Address: {short_address}")
        return format_html(info)

    phone_and_address.short_description = "Contact & Address"

    def undelivered_value(self, obj):
        return f"{obj.supp_total_undelivered_value:,.2f}"

    undelivered_value.short_description = "Undelivered Value"


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "po_number",
        "supplier",
        "order_date",
        "total_amount_display",
        "delivery_status",
        "payment_status",
        "status",
    ]
    list_filter = ["status", "delivery_status", "payment_status", "order_date"]
    search_fields = ["po_number", "supplier__company_name", "supplier__display_name"]
    autocomplete_fields = ["supplier"]
    inlines = [PurchaseOrderItemInline, PaymentInline]
    readonly_fields = ["po_id", "po_number"] + AuditAdminMixin.readonly_fields
    list_select_related = ["supplier"]

    fieldsets = (
        ("Order Header", {"fields": ("po_number", "supplier", "order_date", "status")}),
        ("Tracking", {"fields": ("delivery_status", "payment_status")}),
        (
            "Audit",
            {"fields": AuditAdminMixin.readonly_fields, "classes": ("collapse",)},
        ),
    )

    def total_amount_display(self, obj):
        return f"{obj.total_amount:,.2f}"

    total_amount_display.short_description = "Total Amount"


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "product",
        "get_po_number",
        "ordered_quantity",
        "received_quantity",
        "unit_price_at_order",
        "status",
    ]
    list_filter = ["status", "created_at", "product"]
    search_fields = ["product__modelname", "purchase_order__po_number"]
    autocomplete_fields = ["product", "purchase_order"]
    list_select_related = ["product", "purchase_order"]
    readonly_fields = ["po_item_id"] + AuditAdminMixin.readonly_fields

    def get_po_number(self, obj):
        return obj.purchase_order.po_number

    get_po_number.short_description = "PO Number"


@admin.register(Payment)
class PaymentAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "trxn_ref",
        "purchase_order",
        "amount_paid",
        "payment_method",
        "payment_date",
        "status",
    ]
    list_filter = ["status", "payment_method", "payment_date"]
    search_fields = ["trxn_ref", "purchase_order__po_number"]
    autocomplete_fields = ["purchase_order"]
    readonly_fields = ["payment_id", "trxn_ref"] + AuditAdminMixin.readonly_fields

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("purchase_order")


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "gr_number",
        "purchase_order",
        "delivery_date",
        "received_by",
        "received_quantity_display",
        "status",
    ]
    list_filter = ["status", "delivery_date"]
    search_fields = ["gr_number", "purchase_order__po_number"]
    autocomplete_fields = ["purchase_order", "received_by"]
    inlines = [GoodsReceiptItemInline]
    readonly_fields = ["receipt_id", "gr_number"] + AuditAdminMixin.readonly_fields

    def received_quantity_display(self, obj):
        return obj.received_quantity

    received_quantity_display.short_description = "Total Qty"


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "get_gr_number",
        "product",
        "received_quantity",
        "unit_cost_at_receipt",
        "allocated_delivery_cost_per_unit",
        "goods_receipt__delivery_date",
        "is_reversal",
    ]
    list_filter = [
        "product__modelname",
        "received_quantity",
    ]
    search_fields = ["goods_receipt__gr_number", "product__modelname"]
    autocomplete_fields = ["goods_receipt", "product", "purchase_order_item"]
    readonly_fields = ["receipt_item_id", "reverses"] + AuditAdminMixin.readonly_fields
    list_select_related = ["goods_receipt", "product"]

    def get_gr_number(self, obj):
        return obj.goods_receipt.gr_number

    get_gr_number.short_description = "GR Number"

    def is_reversal(self, obj):
        return bool(obj.reverses)

    is_reversal.boolean = True
    is_reversal.short_description = "Reversal?"
