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
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name


class Sale(models.Model):
    STATUS = ['pending', 'completed', 'cancelled', 'voided']

    sale_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='customer_sales')
    sale_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.sale_id
    

class SaleItem(models.Model):
    STATUS = ['pending', 'fulfilled', 'cancelled', 'voided']

    sale_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='sale_item')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    sold_quantity = models.IntegerField(max_length=20)
    unit_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    serial_item_id = models.ForeignKey(SerializedInventory, on_delete=models.PROTECT, related_name='sale_items', null=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.sale_item_id
    
    class Meta:
        constraints = [
            CheckConstraint (
                check= (Q(sold_quantity__gt=0, unit_selling_prive__gt=0))
            )
        ]


class CustomerTransaction(models.Model):
    TRANSACTION_TYPE = ['deposit', 'withdrawal', 'sale payment']
    FLOW_DIRECTION = ['in', 'out']
    DEPOSIT_PURPOSE = ['normal deposit', 'buy goods', 'covert to cfa']
    PAYMENT_METHOD = ['cash', 'transfer']
    STATUS = ['completed', 'voided']

    def generate_trxn_ref():
        return f"CS-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    transaction_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='customer_trxns')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='sale_trxn', null=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    flow_direction = models.CharField(max_length=10, choices=FLOW_DIRECTION)
    deposit_purpose = models.CharField(max_length=20, blank=True, null=True, choices=DEPOSIT_PURPOSE)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    trxn_ref = models.CharField(max_length=50, editable=False, unique=True, default=generate_trxn_ref)
    transaction_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default='completed', choices=STATUS)
    remark = models.TextField(max_length=255, default='', blank=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

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
                check=(Q(amount_gt=0)), name='chk_positive_amount'
            ),
        ]
