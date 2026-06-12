from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Brand,
    Product,
    Inventory,
    InventoryTransaction,
    Transformation,
    TransformationItem,
)
from django.utils.formats import number_format

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
        """Auto-populate created_by and updated_by."""
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """Auto-populate created_by/updated_by for Inlines."""
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:
                instance.created_by = request.user
            instance.updated_by = request.user
            instance.save()
        formset.save_m2m()


# --- Inlines ---


class InventoryInline(admin.StackedInline):
    model = Inventory
    readonly_fields = [
        "quantity",
        "weighted_average_cost",
        "inventory_id",
    ] + AuditAdminMixin.readonly_fields
    can_delete = False
    extra = 0
    classes = ["collapse"]
    verbose_name = "Current Inventory State"
    verbose_name_plural = "Inventory"

    def has_add_permission(self, request, obj=None):
        return False


class TransformationItemInline(admin.TabularInline):
    model = TransformationItem
    fields = [
        "source_product",
        "target_product",
        "engine_number",
        "chassis_number",
        "allocated_service_fee",
        "status",
    ]
    autocomplete_fields = ["source_product", "target_product"]
    extra = 0
    show_change_link = True


# --- Admin Registration ---


@admin.register(Brand)
class BrandAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = ["name", "created_at", "total_products"]
    search_fields = ["name"]
    ordering = ["name"]

    def total_products(self, obj):
        return obj.product.count()

    total_products.short_description = "Products"


@admin.register(Product)
class ProductAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "sku",
        "brand",
        "modelname",
        "type_variant",
        "category",
        "status",
        "get_stock_on_hand",
        "average_cost_price_display",
    ]
    list_filter = ["brand", "category", "type_variant", "status"]
    search_fields = ["sku", "modelname", "brand__name"]
    autocomplete_fields = ["brand", "base_product"]
    inlines = [InventoryInline]
    list_select_related = ["brand", "inventory"]
    readonly_fields = AuditAdminMixin.readonly_fields + ["product_id", "sku"]

    fieldsets = (
        ("Identification", {"fields": ("sku", "brand", "modelname", "product_id")}),
        (
            "Details",
            {
                "fields": (
                    "category",
                    "type_variant",
                    "base_product",
                    "status",
                    "description",
                )
            },
        ),
        (
            "Audit",
            {"fields": AuditAdminMixin.readonly_fields, "classes": ("collapse",)},
        ),
    )

    def get_stock_on_hand(self, obj):
        return obj.stock_on_hand

    get_stock_on_hand.short_description = "Stock"

    def average_cost_price_display(self, obj):
        return obj.average_cost_price

    average_cost_price_display.short_description = "Avg Cost"


@admin.register(Inventory)
class InventoryAdmin(AuditAdminMixin, admin.ModelAdmin):

    list_display = [
        "get_product_name",
        "quantity",
        "get_formatted_weighted_average_cost",
        "updated_at",
    ]
    list_filter = [
        "product__modelname",
        "updated_at",
    ]
    search_fields = ["product__modelname", "product__sku", "product__brand__name"]
    list_select_related = ["product", "product__brand"]
    readonly_fields = [
        "inventory_id",
        "product",
        "quantity",
        "weighted_average_cost",
    ] + AuditAdminMixin.readonly_fields

    def get_product_name(self, obj):
        return str(obj.product)

    get_product_name.short_description = "Product"

    def get_formatted_weighted_average_cost(self, obj):
        cost = obj.weighted_average_cost

        if cost is None:
            return "N/A"

        rounded_int_cost = int(round(cost, 0))
        formatted_cost = f"{rounded_int_cost:,}"

        return formatted_cost

    get_formatted_weighted_average_cost.short_description = "Avg. Cost"
    get_formatted_weighted_average_cost.admin_order_field = "weighted_average_cost"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request):
        return False


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "transaction_type",
        "get_product",
        "quantity_change",
        "cost_impact",
        "created_at",
        "source_link",
    ]
    list_filter = ["transaction_type", "created_at"]
    search_fields = ["inventory__product__sku", "inventory__product__modelname"]
    list_select_related = ["inventory", "inventory__product"]

    # Transactions should be immutable logs
    readonly_fields = [f.name for f in InventoryTransaction._meta.fields]

    def has_add_permission(self, request):
        return False

    def get_product(self, obj):
        return obj.inventory.product.sku

    get_product.short_description = "Product SKU"

    def source_link(self, obj):
        # Helper to link to the source object (e.g., Sale, Transformation)
        if obj.source:
            return str(obj.source)
        return "-"

    source_link.short_description = "Source"


@admin.register(Transformation)
class TransformationAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "transformation_number",
        "transformation_date",
        "status",
        "service_fee",
        "item_count",
    ]
    list_filter = ["status", "transformation_date"]
    search_fields = ["transformation_number"]
    inlines = [TransformationItemInline]
    readonly_fields = [
        "transformation_number",
        "transformation_id",
    ] + AuditAdminMixin.readonly_fields

    def item_count(self, obj):
        return obj.transformation_items.count()

    item_count.short_description = "Items"


@admin.register(TransformationItem)
class TransformationItemAdmin(AuditAdminMixin, admin.ModelAdmin):
    list_display = [
        "item_number",
        "transformation__transformation_date",
        "get_transformation",
        "target_product",
        "engine_number",
        "chassis_number",
        "status",
    ]
    list_filter = ["status", "target_product__modelname"]
    search_fields = [
        "item_number",
        "engine_number",
        "chassis_number",
        "transformation__transformation_number",
    ]
    autocomplete_fields = ["transformation", "source_product", "target_product"]
    list_select_related = ["transformation", "target_product", "source_product"]
    readonly_fields = ["item_id", "item_number"] + AuditAdminMixin.readonly_fields

    def get_transformation(self, obj):
        return obj.transformation.transformation_number

    get_transformation.short_description = "Transformation REF"

    fieldsets = (
        ("Linkage", {"fields": ("transformation", "item_number", "status")}),
        ("Product Details", {"fields": ("source_product", "target_product")}),
        ("Unique Identifiers", {"fields": ("engine_number", "chassis_number")}),
        (
            "Financials",
            {"fields": ("allocated_service_fee", "unit_cost_at_transformation")},
        ),
        (
            "Audit",
            {"fields": AuditAdminMixin.readonly_fields, "classes": ("collapse",)},
        ),
    )
