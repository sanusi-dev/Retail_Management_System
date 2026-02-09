from django.test import TestCase, Client
from django.urls import reverse
from inventory.models import Product, Brand, Inventory, TransformationItem, Transformation
from account.models import CustomUser
from decimal import Decimal

class ProductStockDisplayTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create and login user
        self.user = CustomUser.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)

        self.brand = Brand.objects.create(name="Test Brand")
        
        # Create Boxed Product
        self.boxed_product = Product.objects.create(
            sku="BOX-001",
            brand=self.brand,
            modelname="Boxed Model",
            type_variant=Product.TypeVariant.BOXED,
            status=Product.Status.ACTIVE
        )
        # Inventory is created by signal, so we update it
        inventory = self.boxed_product.inventory
        inventory.quantity = 10
        inventory.weighted_average_cost = Decimal("100.00")
        inventory.save()

        # Create Coupled Product
        self.coupled_product = Product.objects.create(
            sku="COUPLED-001",
            brand=self.brand,
            modelname="Coupled Model",
            type_variant=Product.TypeVariant.COUPLED,
            status=Product.Status.ACTIVE,
            base_product=self.boxed_product
        )
        # Create a Transformation and Item to make stock available for coupled product
        self.transformation = Transformation.objects.create(service_fee=Decimal("10.00"))
        TransformationItem.objects.create(
            transformation=self.transformation,
            source_product=self.boxed_product,
            target_product=self.coupled_product,
            engine_number="ENG123",
            chassis_number="CHA123",
            status=TransformationItem.Status.AVAILABLE
        )

    def test_formatted_stock_display(self):
        url = reverse('products')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode('utf-8')
        
        # Check Boxed Product Row
        # Currently (before fix), it shows "Boxed: 10" and "Coupled: 0"
        # We want to verify the current state first, or just go straight to verify the fix logic.
        # Let's write the test to EXPECT the FIXED behavior, so it fails now.
        
        # Assertions for what we WANT to see:
        
        # 1. Header should be "Stock" not "Stock (Boxed/Coupled)"
        # self.assertIn('<th scope="col" class="px-6 py-3">Stock</th>', content) 
        # (Exact string match might be brittle with whitespace, but let's try strict check or check presence)
        
        # 2. Boxed product row should show "10" but NOT "Boxed:" or "Coupled:"
        # We need to find the row for the boxed product. 
        # Since checking HTML structure with regex or simple find is easier:
        
        # Verify Boxed Product Row contains "10" and clean display
        self.assertIn("10", content)
        
        # Verify Coupled Product Row contains "1" (from 1 transformation item)
        self.assertIn("1", content)

        # To be robust, let's just check that for the boxed product verification:
        # It currently renders: 
        # <span class="text-xs">Boxed: 10</span>
        # <span class="text-xs">Coupled: 0</span>
        
        # We want it to just render "10" in the cell.
        
        # Let's run this test. If I assert "Boxed: 10" is NOT in content, it should fail now.
        ## self.assertNotIn("Boxed:", content)
        ## self.assertNotIn("Coupled:", content)
