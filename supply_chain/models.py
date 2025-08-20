from django.db import models
from django.urls import reverse
import uuid
from inventory.models import Product, SerializedInventory
from account.models import CustomUser
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import ValidationError


class Supplier(models.Model):
    supplier_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=255)
    address = models.TextField(blank=True, default="")
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
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def get_absolute_url(self):
        return reverse("supplier_detail", kwargs={"pk": self.pk})

    @property
    def get_edit_url(self):
        return reverse("edit_supplier", kwargs={"pk": self.pk})

    @property
    def get_delete_url(self):
        return reverse("delete_supplier", kwargs={"pk": self.pk})

    @property
    def can_delete(self):
        for related in self._meta.related_objects:
            manager = getattr(self, related.get_accessor_name())
            if manager.exists():
                return False
        return True

    # Total value of undelivered units for this supplier
    @property
    def supp_total_undelivered_value(self):
        total_value = sum(
            [po.po_total_undelivered_value for po in self.purchase_orders.all()]
        )
        return total_value


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_RECEIVED = "partially received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    def gen_po_number():
        return f"PO-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    po_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    po_number = models.CharField(
        max_length=50, editable=False, unique=True, default=gen_po_number
    )
    order_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
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
        return self.po_number

    class Meta:
        ordering = ["-updated_at"]

    # Total value of undelivered units for this purchase order
    @property
    def po_total_undelivered_value(self):
        total_value = sum(
            [po_item.remaining_qty_value for po_item in self.po_items.all()]
        )
        return total_value

    # Total quantity of units received for this purchase order
    @property
    def total_recieved(self):
        total_received = self.po_items.aggregate(
            total=models.Sum(F("reciept_items__received_quantity"))
        )["total"]
        return total_received or 0

    # Total value of all ordered items for this purchase order
    @property
    def total_amount(self):
        total_amount = self.po_items.aggregate(
            total=models.Sum(F("ordered_quantity") * F("unit_price_at_order"))
        )["total"]

        return total_amount

    @property
    def get_absolute_url(self):
        return reverse("po_detail", kwargs={"pk": self.pk})

    @property
    def get_edit_url(self):
        return reverse("edit_po", kwargs={"pk": self.pk})

    @property
    def get_delete_url(self):
        return reverse("delete_po", kwargs={"pk": self.pk})

    @property
    def can_delete(self):
        for related in self._meta.related_objects:
            if (
                related.get_accessor_name() != "po_items"
                and getattr(self, related.get_accessor_name()).exists()
            ):
                return False
        return True


class PurchaseOrderItem(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        PARTIALLY_RECEIVED = "partially received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    po_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="po_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="po_items"
    )
    ordered_quantity = models.IntegerField()
    unit_price_at_order = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
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
        return self.product.modelname

    def save(self, *args, **kwargs):
        if self.ordered_quantity is None or self.ordered_quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        if self.unit_price_at_order is None or self.unit_price_at_order <= 0:
            raise ValidationError("Unit Price must be greater than zero")
        return super().save(*args, **kwargs)

    # Total received qty for an item
    @property
    def received_quantity(self):
        received_total = self.reciept_items.aggregate(
            total_received=models.Sum("received_quantity")
        )["total_received"]

        return received_total or 0

    # Total udelivered qty for an item
    @property
    def remaining_qty(self):
        remaining_qty = self.ordered_quantity - self.received_quantity

        return remaining_qty

    # Total value of udelivered qty for an item
    @property
    def remaining_qty_value(self):
        remaining_qty_value = self.remaining_qty * self.unit_price_at_order

        return remaining_qty_value


class SupplierPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"
        VOIDED = "voided", "Voided"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        TRANSFER = "transfer", "Transfer"

    def generate_trxn_ref():
        return (
            f"SP-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )

    payment_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="supplier_payments"
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod)
    trxn_ref = models.CharField(
        max_length=50, editable=False, unique=True, default=generate_trxn_ref
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.FULFILLED)
    remark = models.TextField(max_length=255, default="", blank=True)
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
        return self.trxn_ref


class GoodsReceipt(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"
        VOIDED = "voided", "Voided"

    receipt_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts"
    )
    delivery_date = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="received_%(class)s_set",
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
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
        return self.receipt_id


class GoodsReceiptItem(models.Model):
    receipt_item_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    goods_reciept = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="reciept_items"
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT, related_name="reciept_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="reciept_items_as_product"
    )
    actual_product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="reciept_items_as_actual_product",
    )
    received_quantity = models.IntegerField()
    serial_item = models.ForeignKey(
        SerializedInventory,
        on_delete=models.PROTECT,
        related_name="reciept_items_as_serial_item",
        null=True,
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
        return self.product.modelname
