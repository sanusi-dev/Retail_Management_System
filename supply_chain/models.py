from django.db import models
from django.urls import reverse
import uuid
from inventory.models import Product, SerializedInventory
from account.models import CustomUser
from django.db.models import F, Sum
from django.utils import timezone
from django.core.exceptions import ValidationError


class Supplier(models.Model):

    class Salutation(models.TextChoices):
        MR = "mr", "Mr."
        MRS = "mrs", "Mrs."
        MISS = "miss", "Miss"
        MS = "ms", "Ms."
        DR = "dr", "Dr."
        PROF = "prof", "Prof."

    supplier_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    firstname = models.CharField(max_length=255, null=True, blank=True)
    lastname = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    salutation = models.CharField(
        max_length=10, choices=Salutation, default=Salutation.MR
    )
    mobile = models.CharField(max_length=20, null=True, blank=True, unique=True)
    work_phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    address = models.TextField(null=True, blank=True, default="")
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
        ordering = ["display_name"]

    def __str__(self):
        return f"{self.salutation.title()} {self.display_name.title()}"

    @property
    def name(self):
        if self.salutation and self.display_name:
            return f"{self.salutation}. {self.display_name}"
        else:
            return f"{self.firstname or ''} {self.lastname or ''}".strip()

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
    class DeliveryStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIALLY_RECEIVED = "partially received", "Partially Received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        FULFILLED = "fulfilled", "Fulfilled"
        PARTIAL = "partial", "Partial"

    def gen_po_number():
        return f"PO-{uuid.uuid4().hex[:8].upper()}"

    po_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_orders"
    )
    po_number = models.CharField(
        max_length=50, editable=False, unique=True, default=gen_po_number
    )
    order_date = models.DateTimeField(default=timezone.now)
    delivery_date = models.DateTimeField(null=True, blank=True)
    delivery_status = models.CharField(
        max_length=20, choices=DeliveryStatus, default=DeliveryStatus.PENDING
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus, default=PaymentStatus.PENDING
    )
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

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
        return f"PO-{self.po_number.split('-')[-1]} | {self.supplier.name.upper()} | ₦{self.total_amount:,.2f} |"

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
            total=Sum(F("receipt_items__received_quantity"))
        )["total"]
        return total_received or 0

    # Total quantity of units ordered for this purchase order
    @property
    def total_ordered(self):
        total_ordered = self.po_items.aggregate(total=Sum(F("ordered_quantity")))[
            "total"
        ]
        return total_ordered or 0

    # Total value of all ordered items for this purchase order
    @property
    def subtotal(self):
        subtotal = self.po_items.aggregate(
            total=Sum(F("ordered_quantity") * F("unit_price_at_order"))
        )["total"]

        return subtotal or 0

    @property
    def total_amount(self):
        total_amount = self.subtotal + self.shipping_cost

        return total_amount or 0

    @property
    def total_payment_made(self):
        total = self.payments.aggregate(total_payment=Sum("amount_paid"))[
            "total_payment"
        ]
        return total or 0

    # @property
    # def get_absolute_url(self):
    #     return reverse("po_detail", kwargs={"pk": self.pk})

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

    def update_payment_status(self):
        if self.total_payment_made == self.total_amount:
            self.payment_status = self.PaymentStatus.FULFILLED.value
        elif self.total_payment_made > 0:
            self.payment_status = self.PaymentStatus.PARTIAL.value
        else:
            self.payment_status = self.PaymentStatus.PENDING.value
        self.save()

    def update_delivery_status(self):
        if self.total_ordered == self.total_recieved:
            self.delivery_status = self.DeliveryStatus.RECEIVED.value
        elif self.total_recieved > 0:
            self.delivery_status = self.DeliveryStatus.PARTIALLY_RECEIVED.value
        else:
            self.delivery_status = self.DeliveryStatus.PENDING
        self.save()


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
        received_total = self.receipt_items.aggregate(
            total_received=Sum("received_quantity")
        )["total_received"]

        return received_total or 0

    # Total udelivered qty for an item
    @property
    def remaining_qty(self):
        remaining_qty = self.ordered_quantity - self.received_quantity

        return remaining_qty or 0

    # Total value of udelivered qty for an item
    @property
    def remaining_qty_value(self):
        remaining_qty_value = self.remaining_qty * self.unit_price_at_order

        return remaining_qty_value


class Payment(models.Model):
    class Status(models.TextChoices):
        PAID = "paid", "Paid"
        VOIDED = "voided", "Voided"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        TRANSFER = "transfer", "Transfer"

    def generate_trxn_ref():
        return f"TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    payment_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="payments"
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod, default=PaymentMethod.CASH
    )
    trxn_ref = models.CharField(
        max_length=50, editable=False, unique=True, default=generate_trxn_ref
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.PAID)
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.purchase_order.update_payment_status()

    class Meta:
        ordering = ["-created_at"]


class GoodsReceipt(models.Model):
    class Status(models.TextChoices):
        PENDING = "received", "Received"
        VOIDED = "voided", "Voided"

    receipt_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    gr_number = models.CharField(max_length=50, unique=True, editable=False)
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts"
    )
    delivery_date = models.DateTimeField(default=timezone.now)
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
        return self.purchase_order.po_number

    class Meta:
        ordering = ["-created_by"]

    @property
    def received_quantity(self):
        total_received = self.receipt_items.aggregate(total=Sum("received_quantity"))[
            "total"
        ]
        return total_received or 0

    def save(self, *args, **kwargs):
        if not self.gr_number:
            self.gr_number = f"GR-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
        self.purchase_order.update_delivery_status()


class GoodsReceiptItem(models.Model):
    receipt_item_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    goods_receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="receipt_items"
    )
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT, related_name="receipt_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="receipt_items"
    )
    received_quantity = models.IntegerField(blank=False)
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
        return f"{self.receipt_item_id}"
