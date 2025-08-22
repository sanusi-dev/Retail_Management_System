from django.db import models
from account.models import CustomUser
import uuid
from django.db.models import Q, CheckConstraint, F
from django.core.exceptions import ValidationError
from django.urls import reverse
from .utils import has_any_children


class Brand(models.Model):
    brand_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)s_set",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)s_set",
    )

    def __str__(self):
        return self.name


class Product(models.Model):
    class Category(models.TextChoices):
        MOTORCYCLE = "motorcycle", "Motorcycle"
        ENGINE = "engine", "Engine"
        SPARE_PART = "spare part", "Spare Part"
        EMPTY_OPTION = "", "Select a Category"

    class TypeVariant(models.TextChoices):
        BOXED = "boxed", "Boxed"
        COUPLED = "coupled", "Coupled"
        EMPTY_OPTION = "", "Select a Type"

    product_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sku = models.CharField(max_length=50, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="product")
    modelname = models.CharField(max_length=255)
    category = models.CharField(
        max_length=20, choices=Category, default=Category.EMPTY_OPTION
    )
    type_variant = models.CharField(
        max_length=20, choices=TypeVariant, default=TypeVariant.EMPTY_OPTION
    )
    description = models.TextField(default="", blank=True)
    base_product = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variants",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)s_set",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)s_set",
    )

    def __str__(self):
        return f"{self.modelname.upper()} - {self.type_variant.upper()}"

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.type_variant == "coupled" and not self.base_product:
            raise ValidationError("Coupled product needs a base product")
        elif self.type_variant == "boxed" and self.base_product:
            raise ValidationError("Boxed product does not need a base product")

        super().save(*args, **kwargs)

    # @property
    # def get_absolute_url(self):
    #     return reverse("product_detail", kwargs={"pk": self.pk})

    @property
    def get_edit_url(self):
        return reverse("edit_product", kwargs={"pk": self.pk})

    @property
    def get_delete_url(self):
        return reverse("delete_product", kwargs={"pk": self.pk})

    @property
    def can_edit(self):
        return not has_any_children(self)

    @property
    def can_delete(self):
        return not has_any_children(self)


class Inventory(models.Model):
    inventory_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="inventories"
    )
    quantity_on_hand = models.IntegerField()
    last_updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.product.modelname


class SerializedInventory(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        SOLD = "sold", "Sold"
        RESERVED = "reserved", "Reserved"
        DAMAGED = "damaged", "Damaged"

    serial_item_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="serialized_products"
    )
    engine_number = models.CharField(max_length=255, unique=True)
    chassis_number = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20, choices=Status, default=Status.AVAILABLE, blank=True
    )
    received_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)s_set",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)s_set",
    )

    def __str__(self):
        return self.product.modelname


class InventoryTransformation(models.Model):
    transformation_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    boxed_product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="boxed_products"
    )
    coupled_product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="coupled_products"
    )
    engine_number = models.CharField(max_length=255, unique=True)
    chassis_number = models.CharField(max_length=255, unique=True)
    transformation_date = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)s_set",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)s_set",
    )

    def __str__(self):
        return self.transformation_id
