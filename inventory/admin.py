from django.contrib import admin
from .models import (
    Brand,
    Product,
    Inventory,
    SerializedInventory,
    InventoryTransformation,
)
from django.core.exceptions import ValidationError


class InventoryInline(admin.TabularInline):
    model = Inventory
    extra = 0
    raw_id_fields = ("product",)


class SerializedInventoryInline(admin.TabularInline):
    model = SerializedInventory
    extra = 0
    raw_id_fields = ("product",)


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
        "created_at",
        "sku",
        "brand",
        "modelname",
        "category",
    )
    list_filter = ("brand", "category", "type_variant", "created_at")
    # list_sort = ("brand", "category", "type_variant", "created_at")
    search_fields = ("sku", "modelname")
    inlines = [InventoryInline, SerializedInventoryInline]
    raw_id_fields = ("brand", "base_product", "created_by", "updated_by")

    def save_model(self, request, obj, form, change):
        if obj.type_variant == "coupled" and not obj.base_product:
            raise ValidationError("Coupled product needs a base product")
        elif obj.type_variant == "boxed" and obj.base_product:
            raise ValidationError("Boxed product does not need a base product")

        super().save_model(request, obj, form, change)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    """
    Custom admin for the Inventory model.
    """

    list_display = ("product", "quantity_on_hand", "last_updated_at")
    list_filter = ("last_updated_at",)
    search_fields = ("product__modelname", "product__sku")
    raw_id_fields = ("product",)


@admin.register(SerializedInventory)
class SerializedInventoryAdmin(admin.ModelAdmin):
    """
    Custom admin for the SerializedInventory model.
    """

    list_display = (
        "product",
        "engine_number",
        "chassis_number",
        "status",
        "received_date",
    )
    list_filter = ("status",)
    search_fields = ("engine_number", "chassis_number", "product__modelname")
    raw_id_fields = ("product", "created_by", "updated_by")


@admin.register(InventoryTransformation)
class InventoryTransformationAdmin(admin.ModelAdmin):
    """
    Custom admin for the InventoryTransformation model.
    """

    list_display = (
        "transformation_id",
        "boxed_product",
        "coupled_product",
        "engine_number",
        "chassis_number",
        "transformation_date",
    )
    search_fields = ("engine_number", "chassis_number")
    raw_id_fields = ("boxed_product", "coupled_product", "created_by", "updated_by")
