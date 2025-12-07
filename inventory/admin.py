from django.contrib import admin
from .models import *
from django.core.exceptions import ValidationError


class TransformationItemInline(admin.TabularInline):
    model = TransformationItem
    fk_name = "transformation"
    extra = 1
    raw_id_fields = (
        "source_product",
        "target_product",
    )


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """
    Custom admin for the Brand model.
    """

    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
    raw_id_fields = ("created_by", "updated_by")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Custom admin for the Product model, including inlines for inventory.
    """

    list_display = (
        "sku",
        "created_at",
        "brand",
        "modelname",
        "category",
    )
    list_filter = ("brand", "category", "type_variant", "created_at")
    list_sort = ("brand", "category", "type_variant", "created_at")
    search_fields = ("sku", "modelname")
    raw_id_fields = ("brand", "base_product", "created_by", "updated_by")
    readonly_fields = [
        "sku",
    ]

    # def save_model(self, request, obj, form, change):
    #     if obj.type_variant == "coupled" and not obj.base_product:
    #         raise ValidationError("Coupled product needs a base product")
    #     elif obj.type_variant == "boxed" and obj.base_product:
    #         raise ValidationError("Boxed product does not need a base product")

    #     super().save_model(request, obj, form, change)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    """
    Custom admin for the Inventory model.
    """

    list_display = (
        "product",
        "quantity",
        "weighted_average_cost",
        "created_at",
        "updated_at",
    )
    list_filter = ("updated_at",)
    search_fields = ("product__modelname", "product__sku")
    raw_id_fields = ("product",)


@admin.register(Transformation)
class TransformationAdmin(admin.ModelAdmin):
    """
    Custom admin for the SerializedInventory model.
    """

    list_display = (
        "transformation_number",
        "service_fee",
        "transformation_date",
        "created_at",
    )
    inlines = [TransformationItemInline]
    search_fields = ("transformation_number",)
    raw_id_fields = ("created_by", "updated_by")


@admin.register(TransformationItem)
class TransformationItemAdmin(admin.ModelAdmin):
    """
    Custom admin for the InventoryTransformation model.
    """

    list_display = (
        "item_number",
        "transformation",
        "source_product",
        "target_product",
        "engine_number",
        "chassis_number",
        "status",
        "created_at",
        "updated_at",
    )
    search_fields = ("engine_number", "chassis_number")
    raw_id_fields = (
        "source_product",
        "target_product",
        "created_by",
        "updated_by",
    )


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "inventory",
        "transaction_type",
        "source_content_type",
        "source_object_id",
        "source",
        "quantity_change",
        "cost_impact",
    )
