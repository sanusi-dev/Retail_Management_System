from django.db import models
from account.models import CustomUser
import uuid
from django.db.models import (
    Sum,
    Q,
    F,
    Subquery,
    OuterRef,
    DecimalField,
    ExpressionWrapper,
    fields,
    Count,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from inventory.models import Product, TransformationItem, Inventory
from django.urls import reverse


class Customer(models.Model):
    customer_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer_number = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
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
        indexes = [
            models.Index(fields=["customer_number"]),
            models.Index(fields=["phone"]),
        ]

    def __str__(self):
        return f"{(self.full_name).title()}"

    @property
    def get_absolute_url(self):
        return reverse("customer_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs):
        if not self.customer_number:
            self.customer_number = f"CUST-{uuid.uuid4().hex[:8].upper()}"

        super().save(*args, **kwargs)


class DepositAccount(models.Model):
    account_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.OneToOneField(
        Customer, on_delete=models.PROTECT, related_name="deposit_account"
    )
    account_number = models.CharField(max_length=30, unique=True, editable=False)
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
        indexes = [
            models.Index(fields=["account_number"]),
        ]

    def __str__(self):
        return f"{self.account_number} - {self.customer.full_name}"

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = f"ACCT-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    @property
    def total_balance(self):
        result = self.transactions.filter(status=Transaction.Status.ACTIVE).aggregate(
            deposits=Coalesce(
                Sum(
                    "amount",
                    filter=Q(transaction_type=Transaction.TransactionType.DEPOSIT),
                ),
                Decimal("0.00"),
            ),
            withdrawals=Coalesce(
                Sum(
                    "amount",
                    filter=Q(
                        transaction_type__in=[
                            Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
                            Transaction.TransactionType.WITHDRAWAL,
                        ]
                    ),
                ),
                Decimal("0.00"),
            ),
        )

        deposits = result["deposits"]
        withdrawals = result["withdrawals"]

        return deposits - withdrawals

    @property
    def purchase_allocated_balance(self):

        total_boxed_and_coupled_delivered_subquery = (
            PurchaseAgreementLineItem.objects.filter(
                line_number=OuterRef("line_number"),
                purchase_agreement__in=self.purchase_agreements.all(),
            )
            .annotate(
                active_boxed_sales=Coalesce(
                    Sum(
                        "boxed_sales__quantity",
                        filter=Q(boxed_sales__sale__status=Sale.Status.ACTIVE),
                    ),
                    0,
                ),
                active_coupled_sales=Coalesce(
                    Count(
                        "coupled_sales",
                        filter=Q(coupled_sales__sale__status=Sale.Status.ACTIVE),
                    ),
                    0,
                ),
            )
            .annotate(
                total_valid_delivery=F("active_boxed_sales") + F("active_coupled_sales")
            )
            .values("total_valid_delivery")
        )

        annotated_items = (
            PurchaseAgreementLineItem.objects.filter(
                purchase_agreement__in=self.purchase_agreements.all(),
                is_current_version=True,
            )
            .exclude(purchase_agreement__status=PurchaseAgreement.Status.CANCELLED)
            .annotate(
                total_delivered=Coalesce(
                    Subquery(
                        total_boxed_and_coupled_delivered_subquery,
                        output_field=DecimalField(),
                    ),
                    Decimal("0.00"),
                )
            )
        )

        purchase_total_allocated = annotated_items.aggregate(
            total=Sum(
                (F("quantity_ordered") - F("total_delivered")) * F("price_per_unit")
            )
        )["total"] or Decimal("0.00")

        return purchase_total_allocated

    @property
    def cfa_allocated_balance(self):
        annotated_agreements = self.cfa_agreements.exclude(
            status=CfaAgreement.Status.CANCELLED
        ).annotate(
            fulfilled_value_naira=Coalesce(
                Sum(
                    F("cfa_fulfillments__cfa_amount_disbursed")
                    * (F("exchange_rate") / 1000),
                    filter=Q(cfa_fulfillments__status="ACTIVE"),
                    output_field=DecimalField(),
                ),
                Decimal("0.00"),
            )
        )

        total_remaining = annotated_agreements.aggregate(
            total=Sum(F("amount_allocated") - F("fulfilled_value_naira"))
        )["total"]

        return total_remaining or Decimal("0.00")

    @property
    def allocated_balance(self):
        return self.purchase_allocated_balance + self.cfa_allocated_balance

    @property
    def available_balance(self):
        return self.total_balance - self.allocated_balance


class Transaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = "deposit", "Deposit"
        WITHDRAWAL = "withdrawal", "Withdrawal"
        FULFILLMENT_WITHDRAWAL = "fulfillment", "Fulfillment"
        DEPOSIT_REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        VOIDED = "voided", "Voided"

    transaction_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    account = models.ForeignKey(
        DepositAccount, on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_type = models.CharField(max_length=30, choices=TransactionType)
    amount = models.DecimalField(
        max_digits=15, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    reference_number = models.CharField(max_length=50, unique=True, editable=False)
    source_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.CASCADE
    )
    source_object_id = models.UUIDField(null=True, blank=True)
    source = GenericForeignKey("source_content_type", "source_object_id")
    note = models.TextField(blank=True)
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
        return f"{self.reference_number}"

    def clean(self):
        if self.transaction_type == self.TransactionType.WITHDRAWAL:
            print("yes")
            balance = self.account.available_balance

            if not self._state.adding:
                original_txn = Transaction.objects.get(
                    reference_number=self.reference_number
                )
                balance += original_txn.amount

            if self.amount > balance:
                print("yes")
                raise ValidationError(
                    {
                        "amount": f"Insufficient funds. Available: {balance:,.2f}, Requested: {self.amount:,.2f}"
                    }
                )

        if not self._state.adding:
            original = Transaction.objects.get(pk=self.pk)
            if (
                original.amount != self.amount
                or original.transaction_type != self.transaction_type
            ):
                raise ValidationError(
                    "You cannot modify the Amount or Type of an existing transaction. Void it and create a new one."
                )

        if self.status == self.Status.VOIDED:
            if self.transaction_type in [
                self.TransactionType.FULFILLMENT_WITHDRAWAL,
                self.TransactionType.DEPOSIT_REFUND,
            ]:
                raise ValidationError(
                    "You cannot manually void a Fulfillment or Refund transaction"
                    "Please Void the original Sale/Fulfillment record instead."
                )

        if not self._state.adding and self.status == self.Status.VOIDED:
            original = Transaction.objects.get(pk=self.pk)

            if original.status == self.Status.ACTIVE:
                if self.transaction_type == self.TransactionType.DEPOSIT:
                    current_available = self.account.available_balance
                    projected_balance = current_available - original.amount

                    if projected_balance < 0:
                        raise ValidationError(
                            f"Cannot void this deposit of NGN {original.amount:,.2f}. "
                            f"The customer has active Agreements utilizing these funds. "
                            f"Current Available: NGN {current_available:,.2f}. "
                            "Please cancel/void the relevant Agreements first to free up allocation."
                        )

    def save(self, *args, **kwargs):
        if not self.reference_number:
            year = timezone.now().year

            type_prefix = {
                self.TransactionType.DEPOSIT: "DEP",
                self.TransactionType.WITHDRAWAL: "WTH",
                self.TransactionType.FULFILLMENT_WITHDRAWAL: "FUL",
            }.get(self.transaction_type, "TXN")

            unique_id = uuid.uuid4().hex[:3].upper()
            self.reference_number = f"{type_prefix}-{year}-{unique_id}"

        self.full_clean()
        super().save(*args, **kwargs)


class PurchaseAgreement(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED", "Partially Fulfilled"
        FULFILLED = "FULFILLED", "Fulfilled"
        CANCELLED = "CANCELLED", "Cancelled"

    purchase_agreement_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    purchase_agreement_number = models.CharField(
        max_length=30, unique=True, editable=False
    )
    account = models.ForeignKey(
        DepositAccount, on_delete=models.PROTECT, related_name="purchase_agreements"
    )
    date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=30, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)ss",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)ss",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        date_str = self.date.strftime("%d/%m")

        remaining_items = []
        for item in self.agreement_line_items.all():
            if item.remaining_quantity > 0:
                remaining_items.append(
                    f"{item.product.modelname.upper()} ({item.remaining_quantity:.0f})"
                )

        # Join them, but don't let the string get too long
        if remaining_items:
            items_str = " | ".join(remaining_items)
            if len(items_str) > 50:
                items_str = items_str[:47] + "..."
        else:
            items_str = "Fully Fulfilled"

        return f"{self.account.customer.full_name} - {self.purchase_agreement_number} [{date_str}] • {items_str}"

    @property
    def total_allocated_amount(self):
        amount = self.agreement_line_items.aggregate(
            total=Sum(F("quantity_ordered") * F("price_per_unit"))
        )
        return amount["total"] or Decimal("0.00")

    @property
    def total_quantity_ordered(self):
        amount = self.agreement_line_items.aggregate(total=Sum(F("quantity_ordered")))[
            "total"
        ]
        return amount or Decimal("0.00")

    @property
    def total_quantity_fulfilled(self):
        total_boxed_and_coupled_sale = self.agreement_sales.aggregate(
            total=Sum(F("boxed_sales__quantity"), default=0)
            + Count("coupled_sales", distinct=True)
        )["total"]

        return total_boxed_and_coupled_sale

    @property
    def total_received_percent(self):
        fulfilled = (
            Decimal(str(self.total_quantity_fulfilled))
            if self.total_quantity_fulfilled is not None
            else Decimal("0.00")
        )
        ordered = self.total_quantity_ordered

        if ordered == Decimal("0.00"):
            return Decimal("0.00")

        result = (fulfilled / ordered) * 100
        rounded_result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return rounded_result

    @property
    def can_edit(self):
        if self.total_quantity_fulfilled == 0:
            return True
        return False

    @property
    def can_cancel(self):
        if self.status != self.Status.CANCELLED and self.status == self.Status.ACTIVE:
            return True
        return False

    def update_status(self):

        if self.total_quantity_fulfilled == Decimal("0.00"):
            self.status = self.Status.ACTIVE
        elif self.total_quantity_fulfilled < self.total_quantity_ordered:
            self.status = self.Status.PARTIALLY_FULFILLED
        elif self.total_quantity_fulfilled == self.total_quantity_ordered:
            self.status = self.Status.FULFILLED
        else:
            self.status = self.Status.CANCELLED

        self.save(update_fields=["status"])

    def save(self, *args, **kwargs):
        if not self.purchase_agreement_number:
            self.purchase_agreement_number = f"PUR-{uuid.uuid4().hex[:8].upper()}"

        super().save(*args, **kwargs)


class PurchaseAgreementLineItem(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED", "Partially Fulfilled"
        FULFILLED = "FULFILLED", "Fulfilled"
        VOIDED = "VOIDED", "Voided"
        CANCELLED = "CANCELLED", "Cancelled"

    line_item_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    purchase_agreement = models.ForeignKey(
        PurchaseAgreement, on_delete=models.CASCADE, related_name="agreement_line_items"
    )
    line_number = models.CharField(max_length=20, editable=False)
    product = models.ForeignKey(
        "inventory.Product",
        on_delete=models.PROTECT,
        related_name="purchase_agreement_items",
    )
    quantity_ordered = models.IntegerField()
    price_per_unit = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=30, choices=Status, default=Status.ACTIVE)
    version = models.PositiveIntegerField(default=1)
    is_current_version = models.BooleanField(default=True)
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supersedes",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)ss",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)ss",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["purchase_agreement", "line_number", "version"],
                name="unique_line_version",
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.purchase_agreement} - {self.line_number} - {self.product}"

    @property
    def quantity_fulfilled_accross_all_versions(self):
        """Sum ALL fulfillments for this line number across all versions"""

        total_boxed_sale = (
            BoxedSale.objects.filter(
                agreement_line_item__line_number=self.line_number,
                agreement_line_item__purchase_agreement=self.purchase_agreement,
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        total_coupled_sale = CoupledSale.objects.filter(
            agreement_line_item__line_number=self.line_number,
            agreement_line_item__purchase_agreement=self.purchase_agreement,
        ).count()

        return total_boxed_sale + total_coupled_sale

    @property
    def remaining_quantity(self):
        """Current version quantity - all historical fulfillments"""
        return self.quantity_ordered - self.quantity_fulfilled_accross_all_versions

    @property
    def total_line(self):
        return self.quantity_ordered * self.price_per_unit

    def update_status(self):

        if self.quantity_fulfilled_accross_all_versions == 0:
            self.status = self.Status.ACTIVE
        elif self.quantity_fulfilled_accross_all_versions < self.quantity_ordered:
            self.status = self.Status.PARTIALLY_FULFILLED
        elif self.quantity_fulfilled_accross_all_versions == self.quantity_ordered:
            self.status = self.Status.FULFILLED
        else:
            self.status = self.Status.VOIDED

        self.save(update_fields=["status"])

    def save(self, *args, **kwargs):
        if not self.line_number:
            self.line_number = f"AGR-V{self.version}-{uuid.uuid4().hex[:4].upper()}"

        self.full_clean()
        super().save(*args, **kwargs)


class CfaAgreement(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED", "Partially Fulfilled"
        FULFILLED = "FULFILLED", "Fulfilled"
        CANCELLED = "CANCELLED", "Cancelled"

    cfa_agreement_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    cfa_agreement_number = models.CharField(max_length=50, unique=True, editable=False)
    amount_allocated = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1000.00"))],
    )
    account = models.ForeignKey(
        DepositAccount, on_delete=models.PROTECT, related_name="cfa_agreements"
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("1000.00"))],
        null=True,
        blank=True,
        help_text="Naira per XOF 1,000",
    )
    status = models.CharField(max_length=30, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)ss",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)ss",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.cfa_agreement_number} - NGN{self.amount_allocated:,.2f}"

    @property
    def expected_cfa_amount(self):
        if self.exchange_rate and self.exchange_rate > 0:
            result = (self.amount_allocated / self.exchange_rate) * Decimal("1000")

            # Round to the nearest 100
            rounded_result = result.quantize(Decimal("100"), rounding=ROUND_HALF_UP)
            return rounded_result

        return Decimal("0.00")

    @property
    def total_fulfilled_cfa(self):
        total = self.cfa_fulfillments.filter(
            status=CfaFulfillment.Status.ACTIVE
        ).aggregate(total=Sum("cfa_amount_disbursed"))["total"] or Decimal("0.00")

        # Round the aggregate sum to the nearest 100
        rounded_total = total.quantize(Decimal("100"), rounding=ROUND_HALF_UP)

        return rounded_total

    @property
    def total_cfa_disbursed_percent(self):
        if self.expected_cfa_amount > Decimal("0"):
            result = (self.total_fulfilled_cfa / self.expected_cfa_amount) * 100
            rounded_result = result.quantize(Decimal("100"), rounding=ROUND_HALF_UP)
            return rounded_result

        return Decimal("0.00")

    @property
    def remaining_cfa(self):
        result = self.expected_cfa_amount - self.total_fulfilled_cfa
        rounded_result = result.quantize(Decimal("100"), rounding=ROUND_HALF_UP)
        return rounded_result

    @property
    def can_cancel(self):
        if self.status == self.Status.CANCELLED or self.status != self.Status.ACTIVE:
            return False
        return True

    @property
    def can_edit(self):
        if self.status == self.Status.ACTIVE and self.status != self.Status.CANCELLED:
            return True
        return False

    def update_status(self):
        # Define a tiny margin of error (e.g., half a cent, or smaller)
        # Anything less than this margin should be treated as fully fulfilled.
        EPSILON = Decimal("100")

        remaining_precise = self.expected_cfa_amount - self.total_fulfilled_cfa

        if self.total_fulfilled_cfa == Decimal("0.00"):
            self.status = self.Status.ACTIVE

        elif remaining_precise > EPSILON:
            self.status = self.Status.PARTIALLY_FULFILLED

        else:
            self.status = self.Status.FULFILLED

        self.save(update_fields=["status"])

    def clean(self):
        if self.account.available_balance < self.amount_allocated:
            raise ValidationError(
                {
                    "amount_allocated": f"Customer has insufficient allocation balance. Available: {self.account.available_balance:,.2f}"
                }
            )

    def save(self, *args, **kwargs):
        if not self.cfa_agreement_number:
            self.cfa_agreement_number = f"CFA-{uuid.uuid4().hex[:4].upper()}"

        super().save(*args, **kwargs)


class CfaFulfillment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        VOIDED = "VOIDED", "Voided"

    fulfillment_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    fulfillment_number = models.CharField(max_length=20, unique=True, editable=False)
    cfa_agreement = models.ForeignKey(
        CfaAgreement,
        on_delete=models.PROTECT,
        related_name="cfa_fulfillments",
    )
    date = models.DateTimeField(default=timezone.now)
    cfa_amount_disbursed = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_%(class)ss",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_%(class)ss",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.fulfillment_number}"

    @property
    def cfa_amount_disbursed_to_naira(self):
        amount_in_naira = self.cfa_amount_disbursed * (
            self.cfa_agreement.exchange_rate / 1000
        )

        rounded_amount = amount_in_naira.quantize(
            Decimal("100"), rounding=ROUND_HALF_UP
        )
        return rounded_amount

    def clean(self):
        if self.cfa_amount_disbursed > self.cfa_agreement.remaining_cfa:
            raise ValidationError(
                {
                    "cfa_amount_disbursed": f"Fulfillment amount exceeds remaining CFA. Remaining amount: {self.cfa_agreement.remaining_cfa:,.2f}"
                }
            )

    def save(self, *args, **kwargs):
        if not self.fulfillment_number:
            self.fulfillment_number = f"CFA-FUL-{uuid.uuid4().hex[:4].upper()}"

        super().save(*args, **kwargs)


class Sale(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        VOIDED = "voided", "Voided"

    class PaymentMethod(models.TextChoices):
        BANK_TRANSFER = "bank transfer", "Bank Transfer"
        CASH = "cash", "Cash"
        FROM_DEPOSIT = "from deposit", "From Deposit"

    sale_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sale_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, related_name="customer_sales"
    )
    payment_method = models.CharField(
        max_length=50, choices=PaymentMethod, default=PaymentMethod.BANK_TRANSFER
    )
    agreement = models.ForeignKey(
        PurchaseAgreement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="agreement_sales",
        limit_choices_to=~Q(
            status__in=[
                PurchaseAgreement.Status.FULFILLED,
                PurchaseAgreement.Status.CANCELLED,
            ]
        ),
    )

    sale_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.ACTIVE)
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
        return self.sale_number

    @property
    def sales_total(self):
        coupled_sale_total = self.coupled_sales.aggregate(total=Sum("price"))[
            "total"
        ] or Decimal("0.00")
        boxed_sale_total = self.boxed_sales.aggregate(
            total=Sum(F("price") * F("quantity"))
        )["total"] or Decimal("0.00")

        total_sales_amount = coupled_sale_total + boxed_sale_total
        return total_sales_amount

    @property
    def sales_items_count(self):
        coupled_sale_total = self.coupled_sales.count()
        boxed_sale_total = self.boxed_sales.aggregate(total=Sum("quantity"))["total"]

        total_sales_amount = coupled_sale_total + boxed_sale_total
        return total_sales_amount

    def clean(self):
        if self.payment_method == self.PaymentMethod.FROM_DEPOSIT:
            if not self.agreement:
                raise ValidationError(
                    {
                        "agreement": "An agreement must be selected when the payment method is 'From Deposit'."
                    }
                )
        if self.agreement and self.payment_method != self.PaymentMethod.FROM_DEPOSIT:
            raise ValidationError(
                {
                    "agreement": "An agreement is not required for sales that is not 'From deposit'"
                }
            )
        if self.agreement:
            if self.customer != self.agreement.account.customer:
                raise ValidationError(
                    {"customer": "This sales is not assigned to right customer."}
                )

    def save(self, *args, **kwargs):
        if not self.sale_number:
            self.sale_number = f"SALE-{uuid.uuid4().hex[:8].upper()}"

        self.full_clean()
        super().save(*args, **kwargs)


class CoupledSale(models.Model):
    coupled_sale_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    coupled_sale_number = models.CharField(max_length=20, unique=True, editable=False)
    sale = models.ForeignKey(
        Sale, on_delete=models.CASCADE, related_name="coupled_sales"
    )
    transformation_item = models.ForeignKey(
        TransformationItem,
        on_delete=models.PROTECT,
        related_name="coupled_sales",
        limit_choices_to=~Q(status=TransformationItem.Status.SOLD),
    )
    price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    agreement_line_item = models.ForeignKey(
        PurchaseAgreementLineItem,
        on_delete=models.PROTECT,
        related_name="coupled_sales",
        null=True,
        blank=True,
        limit_choices_to=~Q(
            status__in=[
                PurchaseAgreementLineItem.Status.FULFILLED,
                PurchaseAgreementLineItem.Status.VOIDED,
                PurchaseAgreementLineItem.Status.CANCELLED,
            ]
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_coupled_sales",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_coupled_sales",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["transformation_item"],
                name="unique_transformation_item_per_coupled_sale",
            )
        ]

    def __str__(self):
        return self.coupled_sale_number

    def clean(self):
        # Agreement Mismatch Check
        if self.agreement_line_item and self.sale.agreement:
            if self.agreement_line_item.purchase_agreement != self.sale.agreement:
                raise ValidationError(
                    {
                        "agreement_line_item": "The selected Line Item belongs to a different Agreement than this Sale."
                    }
                )

        # Over-Fulfillment Check
        if self.agreement_line_item:
            remaining = self.agreement_line_item.remaining_quantity
            required_qty = 1

            if remaining < required_qty:
                raise ValidationError(
                    {
                        "agreement_line_item": "This line item is fully fulfilled. Cannot add another Coupled Sale."
                    }
                )

        if self.sale.payment_method != Sale.PaymentMethod.FROM_DEPOSIT:
            if self.price is None:
                raise ValidationError(
                    {"price": "Price is required for this payment method."}
                )

    def save(self, *args, **kwargs):
        if not self.coupled_sale_number:
            self.coupled_sale_number = f"C-SALE-{uuid.uuid4().hex[:8].upper()}"

        if self.sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            if self.agreement_line_item:
                self.price = self.agreement_line_item.price_per_unit

        self.full_clean()
        super().save(*args, **kwargs)


class BoxedSale(models.Model):
    boxed_sale_id = models.UUIDField(
        default=uuid.uuid4, primary_key=True, editable=False
    )
    boxed_sale_number = models.CharField(max_length=20, unique=True, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="boxed_sales")
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="boxed_sales",
        limit_choices_to=Q(type_variant=Product.TypeVariant.BOXED),
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    agreement_line_item = models.ForeignKey(
        PurchaseAgreementLineItem,
        on_delete=models.PROTECT,
        related_name="boxed_sales",
        null=True,
        blank=True,
        limit_choices_to=~Q(
            status__in=[
                PurchaseAgreementLineItem.Status.FULFILLED,
                PurchaseAgreementLineItem.Status.VOIDED,
                PurchaseAgreementLineItem.Status.CANCELLED,
            ]
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_boxed_sales",
    )
    updated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_boxed_sales",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.boxed_sale_number

    def clean(self):
        if not self.product:
            return
        if not self.quantity:
            return

        try:
            inventory = self.product.inventory
        except Inventory.DoesNotExist:
            raise ValidationError(
                {
                    "product": f"No inventory record exists for {self.product.modelname}. Please initialize stock first."
                }
            )

        available_stock = inventory.quantity

        if self._state.adding:
            try:
                original_sale = BoxedSale.objects.get(pk=self.pk)
                available_stock += original_sale.quantity
            except BoxedSale.DoesNotExist:
                pass

        if self.quantity > available_stock:
            raise ValidationError(
                {
                    "quantity": f"Insufficient Stock. Available: {available_stock}, Requested: {self.quantity}"
                }
            )

        # Agreement Mismatch Check
        if self.agreement_line_item and self.sale.agreement:
            if self.agreement_line_item.purchase_agreement != self.sale.agreement:
                raise ValidationError(
                    {
                        "agreement_line_item": "The selected Line Item belongs to a different Agreement than this Sale."
                    }
                )

        if self.product and self.agreement_line_item:
            if self.product != self.agreement_line_item.product:
                raise ValidationError(
                    {
                        "product": "Product mismatch, please select a product that is same with the agreement line item.."
                    }
                )

        # Over-Fulfillment Check
        if self.agreement_line_item:
            remaining = self.agreement_line_item.remaining_quantity

            # Determine the quantity currently saved in the DB for THIS specific sale
            current_db_qty = 0
            if not self._state.adding:
                try:
                    current_db_qty = BoxedSale.objects.get(
                        boxed_sale_number=self.boxed_sale_number
                    ).quantity
                except BoxedSale.DoesNotExist:
                    pass

            available_pool = remaining + current_db_qty

            if self.quantity > available_pool:
                raise ValidationError(
                    {
                        "quantity": f"Over-fulfillment detected! You are trying to sell {self.quantity}, but only {available_pool} remains on this line item."
                    }
                )

        if self.sale.payment_method != Sale.PaymentMethod.FROM_DEPOSIT:
            if self.price is None:
                raise ValidationError(
                    {"price": "Price is required for this payment method."}
                )

    def save(self, *args, **kwargs):
        if not self.boxed_sale_number:
            self.boxed_sale_number = f"B-SALE-{uuid.uuid4().hex[:8].upper()}"

        if self.sale.payment_method == Sale.PaymentMethod.FROM_DEPOSIT:
            if self.agreement_line_item:
                self.price = self.agreement_line_item.price_per_unit

        self.full_clean()
        super().save(*args, **kwargs)
