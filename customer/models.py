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
    address = models.TextField(blank=True, default='')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.name


class Sale(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        VOIDED = 'voided', 'Voided'

    sale_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='customer_sales')
    sale_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.sale_id
    

class SaleItem(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        FULFILLED = 'fulfilled', 'Fulfilled'
        CANCELLED = 'cancelled', 'Cancelled'
        VOIDED = 'voided', 'Voided'

    sale_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='sale_item')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    sold_quantity = models.IntegerField()
    unit_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    serial_item_id = models.ForeignKey(SerializedInventory, on_delete=models.PROTECT, related_name='sale_items', null=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.sale_item_id
    
    class Meta:
        constraints = [
            CheckConstraint (
                check= (Q(sold_quantity__gt=0, unit_selling_price__gt=0)),
                name='chk_sales_items_positive_amount'
            )
        ]


class CustomerTransaction(models.Model):
    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        SALE_PAYMENT = 'sale payment', 'Sale Payment'

    class FlowDirection(models.TextChoices):
        IN = 'in', 'In'
        OUT = 'out', 'Out'

    class DepositPurpose(models.TextChoices):
        NORMAL_DEPOSIT = 'normal deposit', 'Normal Deposit'
        BUY_GOODS = 'buy goods', 'Buy Goods'
        CONVERT_TO_CFA = 'convert to cfa', 'Convert to CFA'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        TRANSFER = 'transfer', 'Transfer'

    class Status(models.TextChoices):
        COMPLETED = 'completed', 'Completed'
        VOIDED = 'voided', 'Voided'

    def generate_trxn_ref():
        return f"CS-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    transaction_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='customer_trxns')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='sale_trxn', null=True)
    transaction_type = models.CharField(max_length=20, choices=TransactionType)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    flow_direction = models.CharField(max_length=10, choices=FlowDirection)
    deposit_purpose = models.CharField(max_length=20, blank=True, null=True, choices=DepositPurpose)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod)
    trxn_ref = models.CharField(max_length=50, editable=False, unique=True, default=generate_trxn_ref)
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='completed', choices=Status)
    remark = models.TextField(max_length=255, default='', blank=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.trxn_ref
    
    class Meta:
        constraints = [
            CheckConstraint (
                check=(
                    Q(transaction_type='deposit', deposit_purpose__isnull=False)| 
                    (~Q(transaction_type='deposit') & Q(deposit_purpose__isnull=True))
                ), name='chk_deposit_purpose_logic'
            ),

            CheckConstraint (
                check=(
                    Q(transaction_type='sale payment', sale_id__isnull=False)| 
                    (~Q(transaction_type='sale payment') & Q(sale_id__isnull=True))
                ), name='chk_sale_payment_logic'
            ),
            CheckConstraint (
                check=(Q(amount__gt=0)), name='chk_positive_amount'
            ),
        ]
