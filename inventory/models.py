from django.db import models
from account.models import CustomUser
import uuid
from django.db.models import F, Sum, Count
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from django.urls import reverse


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

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    product_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sku = models.CharField(max_length=50, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="product")
    modelname = models.CharField(max_length=255)
    category = models.CharField(
        max_length=20, choices=Category, default=Category.EMPTY_OPTION
    )
    type_variant = models.CharField(
        max_length=20, choices=TypeVariant, default=TypeVariant.BOXED
    )
    description = models.TextField(default="", blank=True)
    base_product = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variants",
    )
    status = models.CharField(max_length=10, choices=Status, default=Status.ACTIVE)
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
        return f"{self.brand.name.upper()} - {self.modelname.upper()}"

    @property
    def name(self):
        return f"{self.modelname}-{self.type_variant}".upper()

    class Meta:
        ordering = ["brand"]

    def save(self, *args, **kwargs):

        if self.type_variant == "coupled" and not self.base_product:
            raise ValidationError("Coupled product needs a base product")
        elif self.type_variant == "boxed" and self.base_product:
            raise ValidationError("Boxed product does not need a base product")

        if self.modelname and self.brand:
            self.sku = f"{str(self.brand)}-{self.modelname}-{self.type_variant}"

        super().save(*args, **kwargs)

    @property
    def average_cost_price(self):
        aggregation = self.po_items.aggregate(
            total_sum=Sum("unit_price_at_order"), total_count=Count("pk")
        )

        total_sum = aggregation["total_sum"] or 0
        total_count = aggregation["total_count"] or 0

        if total_count > 0:
            avg = total_sum / total_count
            return f"{avg:,.2f}"
        return "0.00"

    @property
    def average_sales_price(self):
        aggregation = self.sale_items.aggregate(
            total_sum=Sum("unit_selling_price"), total_count=Count("pk")
        )

        total_sum = aggregation["total_sum"] or 0
        total_count = aggregation["total_count"] or 0

        if total_count > 0:
            avg = total_sum / total_count
            return f"{avg:,.2f}"
        return "0.00"

    @property
    def total_remaining_qty(self):
        annotated = self.po_items.annotate(
            total_received=Coalesce(Sum("receipt_items__received_quantity"), 0)
        ).annotate(remaining_calc=F("ordered_quantity") - F("total_received"))
        remaining_calc = annotated.aggregate(total=Sum("remaining_calc"))["total"]
        return remaining_calc or 0

    @classmethod
    def get_list_url(cls):
        return reverse("products")

    @property
    def get_absolute_url(self):
        return reverse("product_detail", kwargs={"pk": self.pk})

    @property
    def get_edit_url(self):
        return reverse("edit_product", kwargs={"pk": self.pk})

    @property
    def get_delete_url(self):
        return reverse("delete_product", kwargs={"pk": self.pk})

    @property
    def status_change_url(self):
        return reverse("status_change", kwargs={"pk": self.pk})

    @property
    def overview_url(self):
        return reverse("overview", kwargs={"pk": self.pk})

    @property
    def transaction_url(self):
        return reverse("transaction", kwargs={"pk": self.pk})

    @property
    def can_delete(self):
        for related in self._meta.related_objects:
            manager = getattr(self, related.get_accessor_name())
            if hasattr(manager, "exists") and manager.exists():
                return False
        return True

    # @property
    # def all_goods_receipts(self):
    #     return self.po_items.goods_receipts.all()


class Inventory(models.Model):
    inventory_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity_on_hand = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
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
