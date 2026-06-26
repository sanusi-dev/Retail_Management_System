from django.test import TestCase, Client
from django.urls import reverse
from customer.models import Sale, Customer, Transaction
from inventory.models import Product, Inventory
from supply_chain.models import PurchaseOrder, Payment

from django.contrib.auth import get_user_model

class DashboardViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.dashboard_url = reverse('dashboard')
        User = get_user_model()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')

    def test_dashboard_view_status_code(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')

    def test_dashboard_context(self):
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('daily_sales', response.context)
        self.assertIn('period_sales', response.context)
        self.assertIn('period_gross_profit', response.context)
        self.assertIn('period_net_profit', response.context)
        self.assertIn('total_customers', response.context)
        self.assertIn('low_stock', response.context)

