from django.test import TestCase, Client
from django.urls import reverse
from inventory.models import Product, Brand
from account.models import CustomUser

class ProductSortingTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.force_login(self.user)
        
        self.brand = Brand.objects.create(name="Brand A", created_by=self.user)
        
        # Create products
        self.p1 = Product.objects.create(sku="A-SKU", modelname="Model A", brand=self.brand, created_by=self.user)
        self.p2 = Product.objects.create(sku="B-SKU", modelname="Model B", brand=self.brand, created_by=self.user)
        
    def test_sorting_by_sku_asc(self):
        url = reverse('products')
        response = self.client.get(url, {'sort': 'sku', 'direction': 'asc'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        self.assertEqual(products[0], self.p1)
        self.assertEqual(products[1], self.p2)

    def test_sorting_by_sku_desc(self):
        url = reverse('products')
        response = self.client.get(url, {'sort': 'sku', 'direction': 'desc'})
        self.assertEqual(response.status_code, 200)
        products = list(response.context['products'])
        self.assertEqual(products[0], self.p2)
        self.assertEqual(products[1], self.p1)
        
    def test_htmx_sorting_renders_body_only(self):
        url = reverse('products')
        headers = {'HTTP_HX_REQUEST': 'true'}
        response = self.client.get(url, {'sort': 'sku'}, **headers)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('Model A', content)
        self.assertNotIn('name="q"', content)

    def test_htmx_full_load_renders_content(self):
        url = reverse('products')
        headers = {'HTTP_HX_REQUEST': 'true'}
        response = self.client.get(url, {}, **headers)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('name="q"', content)
