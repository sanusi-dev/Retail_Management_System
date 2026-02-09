from django.test import TestCase, Client
from django.utils import timezone
from inventory.models import Product, Brand, Inventory
from supply_chain.models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem, Supplier
from account.models import CustomUser
from decimal import Decimal
import time

class InventoryUpdateTimestampTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='password')
        self.brand = Brand.objects.create(name="Test Brand")
        self.product = Product.objects.create(
            sku="TEST-SKU", brand=self.brand, modelname="Test Model", created_by=self.user
        )
        # Inventory is created automatically via signal
        self.inventory = Inventory.objects.get(product=self.product)
        
        # Ensure initial updated_at is set and distinct
        self.inventory.updated_at = timezone.now() - timezone.timedelta(days=1)
        self.inventory.save()
        
        self.initial_updated_at = self.inventory.updated_at
        
        self.supplier = Supplier.objects.create(company_name="Test Supplier")
        self.po = PurchaseOrder.objects.create(supplier=self.supplier, created_by=self.user)
        self.po_item = PurchaseOrderItem.objects.create(
            purchase_order=self.po, product=self.product, 
            unit_price_at_order=Decimal("100.00"), ordered_quantity=10
        )
        self.po.status = PurchaseOrder.Status.ACTIVE
        self.po.save()

    def test_goods_receipt_updates_inventory_timestamp(self):
        # Create Goods Receipt
        gr = GoodsReceipt.objects.create(
            purchase_order=self.po, 
            created_by=self.user,
            delivery_cost=Decimal("10.00")
        )
        
        # Create Goods Receipt Item - this triggers the signal
        gri = GoodsReceiptItem.objects.create(
            goods_receipt=gr,
            purchase_order_item=self.po_item,
            product=self.product,
            received_quantity=5,
            unit_cost_at_receipt=Decimal("100.00"),
            created_by=self.user
        )
        
        # Reload inventory
        self.inventory.refresh_from_db()
        
        # Verify quantity updated (should work)
        self.assertEqual(self.inventory.quantity, 5)
        
        # Verify updated_at updated (EXPECT TO FAIL currently)
        self.assertNotEqual(self.inventory.updated_at, self.initial_updated_at)
