from django.db import models
from account.models import CustomUser
import uuid
from django.db.models import *
from django.db.models.functions import Coalesce
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from easyaudit.models import CRUDEvent
from django.utils import timezone
from utils.utils import create_inventory_transaction


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

    class Meta:
        ordering = ["modelname"]

    def __str__(self):
        return f"{self.brand.name.upper()} - {self.modelname.upper()} - {self.type_variant.upper()}"

    @classmethod
    def get_list_url(cls):
        return reverse("products")

    @property
    def name(self):
        return f"{self.modelname}-{self.type_variant}".upper()

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
        return reverse("product_status_change", kwargs={"pk": self.pk})

    @property
    def overview_url(self):
        return reverse("product_overview", kwargs={"pk": self.pk})

    @property
    def transaction_url(self):
        return reverse("product_transaction", kwargs={"pk": self.pk})

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
    def total_remaining_qty(self):
        annotated = self.po_items.annotate(
            total_received=Coalesce(Sum("receipt_items__received_quantity"), 0)
        ).annotate(remaining_calc=F("ordered_quantity") - F("total_received"))
        remaining_calc = annotated.aggregate(total=Sum("remaining_calc"))["total"]
        return remaining_calc or 0

    @property
    def can_delete(self):
        for related in self._meta.related_objects:
            manager = getattr(self, related.get_accessor_name())
            if hasattr(manager, "exists") and manager.exists():
                return False
        return True

    @property
    def stock_on_hand(self):
        return self.inventory.quantity or 0

    @property
    def all_logs(self):
        base_qs = Q(
            content_type=ContentType.objects.get_for_model(self),
            object_id=self.pk,
        )

        related_qs = Q()
        for related in self._meta.related_objects:
            related_model = related.related_model
            related_model_content_type = ContentType.objects.get_for_model(
                related_model
            )
            try:
                related_manager = getattr(self, related.get_accessor_name())
                if not related.one_to_one:
                    related_ids = related_manager.values_list("pk", flat=True)
                    string_ids = [str(pk) for pk in related_ids]
                    if string_ids:
                        related_qs |= Q(
                            content_type=related_model_content_type,
                            object_id__in=string_ids,
                        )
                else:
                    related_qs |= Q(
                        content_type=related_model_content_type,
                        object_id=related_manager.pk,
                    )
            except related.related_model.DoesNotExist:
                pass

        return CRUDEvent.objects.filter(base_qs | related_qs)

    def save(self, *args, **kwargs):

        if self.type_variant == "coupled" and not self.base_product:
            raise ValidationError("Coupled product needs a base product")
        elif self.type_variant == "boxed" and self.base_product:
            raise ValidationError("Boxed product does not need a base product")

        if self.modelname and self.brand:
            sku = f"{self.modelname}-{self.type_variant}"
            if self._state.adding:
                self.sku = sku
            else:
                if self.sku != sku:
                    self.sku = sku

        super().save(*args, **kwargs)


class Inventory(models.Model):
    inventory_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity = models.PositiveIntegerField(default=0)
    weighted_average_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
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

    class Meta:
        ordering = ["-quantity"]

    def __str__(self):
        return self.product.modelname


class InventoryTransaction(models.Model):
    class TransactionType(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        SALE = "sale", "Sale"
        TRANSFORMATION = "transformation", "Transformation"
        RECEIPT_REVERSAL = "receipt_reversal", "Receipt Reversal"
        SALE_REVERSAL = "sale_reversal", "Sale Reversal"
        TRANSFORMATION_REVERSAL = "transformation_reversal", "Transformation Reversal"

    inventory_transaction_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    transaction_type = models.CharField(max_length=30, choices=TransactionType)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    source_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    source_object_id = models.UUIDField()
    source = GenericForeignKey("source_content_type", "source_object_id")
    quantity_change = models.IntegerField()
    cost_impact = models.DecimalField(max_digits=10, decimal_places=2)
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

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.source)


class Transformation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        VOIDED = "voided", "Voided"

    transformation_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    transformation_number = models.CharField(max_length=50, unique=True, editable=False)
    service_fee = models.DecimalField(max_digits=10, decimal_places=2)
    transformation_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=50, choices=Status, default=Status.ACTIVE)
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
        return f"{self.transformation_number.upper()}"

    @classmethod
    def get_list_url(cls):
        return reverse("transformations")

    @property
    def get_absolute_url(self):
        return reverse("transformation_detail", kwargs={"pk": self.pk})

    @property
    def get_void_url(self):
        return reverse("void_transformation", kwargs={"pk": self.pk})

    @property
    def total_transformed_qty(self):
        total = self.transformation_items.count()
        return total or 0

    def save(self, *args, **kwargs):
        if not self.transformation_number:
            self.transformation_number = f"TRF-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class TransformationItem(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        SOLD = "sold", "Sold"
        RESERVED = "reserved", "Reserved"
        VOIDED = "voided", "Voided"

    item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    item_number = models.CharField(max_length=50, unique=True, editable=False)
    transformation = models.ForeignKey(
        Transformation,
        on_delete=models.CASCADE,
        related_name="transformation_items",
    )
    source_product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="transform_from"
    )
    target_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="transform_to",
    )
    engine_number = models.CharField(
        max_length=100, unique=True, null=False, blank=False
    )
    chassis_number = models.CharField(
        max_length=100, unique=True, null=False, blank=False
    )
    allocated_service_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    unit_cost_at_transformation = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00
    )
    status = models.CharField(
        max_length=20, choices=Status, default=Status.AVAILABLE, blank=True
    )
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
        return f"{self.item_number} - {self.target_product.brand} - {self.target_product.modelname.upper()} - ENG: ...{self.engine_number[-5:]} | CHA: ...{self.chassis_number[-5:]}"

    def create_reversal(self):
        inventory = self.source_product.inventory
        inventory.quantity += 1
        inventory.save(update_fields=["quantity"])

        create_inventory_transaction(
            inventory=inventory,
            source=self,
            transaction_type=InventoryTransaction.TransactionType.TRANSFORMATION_REVERSAL,
            quantity_change=1,
            cost_impact=inventory.weighted_average_cost,
        )
        self.status = self.Status.VOIDED
        self.save(update_fields=["status"])

    def save(self, *args, **kwargs):
        if not self.item_number:
            self.item_number = f"ITEM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
