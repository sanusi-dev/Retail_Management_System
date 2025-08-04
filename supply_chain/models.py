from django.db import models
import uuid
from inventory.models import Product, SerializedInventory
from account.models import CustomUser
from django.db.models import Q, CheckConstraint, F
from django.utils import timezone


class Supplier(models.Model):
    supplier_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
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
    

class PurchaseOrder(models.Model):
    STATUS = ['active', 'pending', 'approved', 'partially received', 'received', 'cancelled']

    def gen_po_number():
        return f"PO-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    po_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    po_number = models.CharField(max_length=50, editable=False, unique=True, default=gen_po_number)
    order_date = models.DateTimeField(auto_now_add=True)
    expected_delivery_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.po_number
    
    class Meta:
        constraints = [
            CheckConstraint (
                check=(Q(expected_delivery_date__gte=F('order_date'))),
                name='chk_po_delivery_date'
            ),

            CheckConstraint (
                check=Q(total_amount__gt=0),
                name='chk_po_total_amount'
            )
        ]

class PurchaseOrderItem(models.Model):
    STATUS = ['active', 'pending', 'approved', 'partially received', 'received', 'cancelled']

    po_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='purchase_order_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='purchase_order_items')
    ordered_quantity = models.IntegerField(max_length=20, default=1)
    received_quantity = models.IntegerField(max_length=20, default=0)
    unit_price_at_order = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.product.modelname
    
    class Meta:
        constraints = [
            CheckConstraint (
                check= (
                    Q(ordered_quantity__gt=0, received_quantity__gte=0, unit_price_at_order__gt=0)
                ), name='chk_po_item_positive_values'
            ),

            CheckConstraint (
                check= (
                    Q(received_quantity__lte=F('ordered_quantity'))
                ), name='chk_po_item_received_not_exceed_ordered'
            )
        ]


class SupplierPayment(models.Model):
    PAYMENT_METHOD = ['cash', 'transfer']
    STATUS = ['pending', 'completed', 'voided']

    def generate_trxn_ref():
        return f"SP-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    
    payment_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='supplier_payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    trxn_ref = models.CharField(max_length=50, editable=False, unique=True, default=generate_trxn_ref)
    status = models.CharField(max_length=20, default='completed', choices=STATUS)
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
                check=(Q(amount_paid__gt=0)), 
                name='chk_positive_payment_amount'
            ),
        ]


class GoodsReceipt(models.Model):
    STATUS = ['completed', 'pending', 'cancelled']

    receipt_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='goods_receipts')
    delivery_date = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.receipt_id


class GoodsReceiptItem(models.Model):
    receipt_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    goods_reciept = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='reciept_items')
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name='reciept_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='receipt_items_as_product')
    actual_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='receipt_items_as_actual_product')
    received_quantity = models.IntegerField(max_length=20, default=0)
    serial_item = models.ForeignKey(SerializedInventory, on_delete=models.PROTECT, related_name='receipt_items_as_serial_item', null=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.product.modelname
    
    class Meta:
        constraints = [
            CheckConstraint (
                check= (Q(received_quantity__gte=0)), name='chk_receipt_item_positive_quantity'
            ),
        ]
