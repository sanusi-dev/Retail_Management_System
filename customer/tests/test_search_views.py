from django.test import TestCase, Client
from django.urls import reverse
from customer.models import Customer
from inventory.models import Product, Brand, TransformationItem, Transformation
from account.models import CustomUser

class SearchViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)
        
        # Create Data
        self.customer = Customer.objects.create(full_name="John Doe", phone="1234567890", created_by=self.user)
        
        self.brand = Brand.objects.create(name="Toyota", created_by=self.user)
        self.product = Product.objects.create(
            brand=self.brand, 
            modelname="Camry", 
            sku="CAM-001", 
            created_by=self.user
        )
        # Ensure inventory exists and has stock
        if hasattr(self.product, 'inventory'):
             self.product.inventory.quantity = 100
             self.product.inventory.save()
        else:
             from inventory.models import Inventory
             Inventory.objects.create(product=self.product, quantity=100, created_by=self.user)
        
        self.transformation = Transformation.objects.create(created_by=self.user, service_fee=0)
        
        self.transformation_item = TransformationItem.objects.create(
            transformation=self.transformation,
            source_product=self.product,
            target_product=self.product,
            engine_number="ENG123",
            chassis_number="CHA123",
            created_by=self.user
        )

    def test_search_customers(self):
        response = self.client.get(reverse('search_customers') + '?q=John')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "John Doe")
        self.assertTemplateUsed(response, "partials/search_results_customer.html")

    def test_search_products(self):
        response = self.client.get(reverse('search_products') + '?q=Camry')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camry")
        self.assertTemplateUsed(response, "partials/search_results_product.html")

    def test_search_transformation_items(self):
        # Search by Engine Number
        response = self.client.get(reverse('search_transformation_items') + '?q=ENG123')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ENG123")
        self.assertTemplateUsed(response, "partials/search_results_transformation_item.html")
        
        # Search by Model
        response = self.client.get(reverse('search_transformation_items') + '?q=Camry')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camry")
