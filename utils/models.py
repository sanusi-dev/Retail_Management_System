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


from django.db import models
from account.models import CustomUser
import uuid
from django.db.models import Q, CheckConstraint
from django.utils import timezone
from inventory.models import Product, SerializedInventory


class Customer(models.Model):
    customer_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(max_length=255)
    address = models.TextField(blank=True, default="")
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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


class Sale(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        VOIDED = "voided", "Voided"

    sale_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="customer_sales"
    )
    sale_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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
        return self.sale_id


class SaleItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"
        VOIDED = "voided", "Voided"

    sale_item_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="sale_item")
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name="sale_items"
    )
    sold_quantity = models.IntegerField()
    unit_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    serial_item_id = models.ForeignKey(
        SerializedInventory,
        on_delete=models.PROTECT,
        related_name="sale_items",
        null=True,
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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
        return self.sale_item_id

    class Meta:
        constraints = [
            CheckConstraint(
                check=(Q(sold_quantity__gt=0, unit_selling_price__gt=0)),
                name="chk_sales_items_positive_amount",
            )
        ]


class CustomerTransaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        SALE_PAYMENT = "sale payment", "Sale Payment"

    class FlowDirection(models.TextChoices):
        IN = "in", "In"
        OUT = "out", "Out"

    class DepositPurpose(models.TextChoices):
        NORMAL_DEPOSIT = "normal deposit", "Normal Deposit"
        BUY_GOODS = "buy goods", "Buy Goods"
        CONVERT_TO_CFA = "convert to cfa", "Convert to CFA"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        TRANSFER = "transfer", "Transfer"

    class Status(models.TextChoices):
        COMPLETED = "completed", "Completed"
        VOIDED = "voided", "Voided"

    def generate_trxn_ref():
        return (
            f"CS-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )

    transaction_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    customer = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="customer_trxns"
    )
    sale = models.ForeignKey(
        Sale, on_delete=models.PROTECT, related_name="sale_trxn", null=True
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionType)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    flow_direction = models.CharField(max_length=10, choices=FlowDirection)
    deposit_purpose = models.CharField(
        max_length=20, blank=True, null=True, choices=DepositPurpose
    )
    payment_method = models.CharField(max_length=20, choices=PaymentMethod)
    trxn_ref = models.CharField(
        max_length=50, editable=False, unique=True, default=generate_trxn_ref
    )
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="completed", choices=Status)
    remark = models.TextField(max_length=255, default="", blank=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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

    class Meta:
        constraints = [
            CheckConstraint(
                check=(
                    Q(transaction_type="deposit", deposit_purpose__isnull=False)
                    | (~Q(transaction_type="deposit") & Q(deposit_purpose__isnull=True))
                ),
                name="chk_deposit_purpose_logic",
            ),
            CheckConstraint(
                check=(
                    Q(transaction_type="sale payment", sale_id__isnull=False)
                    | (~Q(transaction_type="sale payment") & Q(sale_id__isnull=True))
                ),
                name="chk_sale_payment_logic",
            ),
            CheckConstraint(check=(Q(amount__gt=0)), name="chk_positive_amount"),
        ]


from django.db import models
import uuid
from customer.models import Customer, Sale
from account.models import CustomUser
from django.db.models import Q, CheckConstraint, F
from django.utils import timezone


class Loan(models.Model):
    class LoanType(models.TextChoices):
        SALES_LOAN = "sales loan", "Sales Loan"
        NORMAL_LOAN = "normal loan", "Normal Loan"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        WRITTEN_OFF = "written off", "Written Off"
        CANCELLED = "cancelled", "Cancelled"

    loan_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="customer_loans"
    )
    sale = models.ForeignKey(
        Sale, on_delete=models.PROTECT, related_name="loan_sales", null=True
    )
    loan_type = models.CharField(max_length=20, choices=LoanType)
    principal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    loan_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status, default="active", blank=True
    )
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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
        return self.loan_id

    class Meta:
        constraints = [
            CheckConstraint(
                check=(
                    Q(loan_type="sales loan", sale_id__isnull=False)
                    | Q(loan_type="normal loan", sale_id__isnull=True)
                ),
                name="chk_loan_type_sale_logic",
            ),
            CheckConstraint(
                check=Q(principal_amount__gt=0), name="chk_positive_principal_amount"
            ),
            CheckConstraint(
                check=(Q(due_date__gte=F("loan_date"))), name="chk_due_date_logic"
            ),
        ]


class LoanRepayments(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        TRANSFER = "transfer", "Transfer"

    def generate_txn_ref(self):
        return (
            f"LP-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )

    repayment_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    loan = models.ForeignKey(
        Loan, on_delete=models.PROTECT, related_name="loan_repayments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(
        max_length=20, default="cash", choices=PaymentMethod
    )
    trxn_ref = models.CharField(
        max_length=50, editable=False, default=generate_txn_ref, unique=True
    )
    remark = models.TextField(blank=True, default="")
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
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

    class Meta:
        constraints = [
            CheckConstraint(
                check=(Q(amount__gt=0)), name="chk_positive_repayment_amount"
            ),
        ]
