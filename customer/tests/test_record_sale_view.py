from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from decimal import Decimal
from customer.models import (
    Customer, DepositAccount, PurchaseAgreement, PurchaseAgreementLineItem,
    Sale, BoxedSale, CoupledSale, Transaction
)
from inventory.models import Product, Brand, Inventory, TransformationItem, Transformation
from django.utils import timezone
import uuid

User = get_user_model()

class RecordSaleViewTests(TestCase):

    def setUp(self):
        # Create User
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

        # Create Inventory Data
        self.brand = Brand.objects.create(name="Test Brand", created_by=self.user)
        self.product = Product.objects.create(
            sku="TEST-PROD-001",
            brand=self.brand,
            modelname="Test Model",
            type_variant=Product.TypeVariant.BOXED,
            created_by=self.user
        )
        # Inventory is created by signal
        self.inventory = Inventory.objects.get(product=self.product)
        self.inventory.quantity = 100
        self.inventory.weighted_average_cost = Decimal("5000.00")
        self.inventory.save()

        self.base_product = Product.objects.create(
             sku="TEST-BASE-001",
             brand=self.brand,
             modelname="Base Model",
             type_variant=Product.TypeVariant.BOXED,
             created_by=self.user
        )
        # Configure base product inventory before transformation
        base_inventory = Inventory.objects.get(product=self.base_product)
        base_inventory.quantity = 10
        base_inventory.weighted_average_cost = Decimal("5000.00")
        base_inventory.save()

        # For coupled items
        self.coupled_product = Product.objects.create(
            sku="TEST-COUPLED-001",
            brand=self.brand,
            modelname="Coupled Model",
            type_variant=Product.TypeVariant.COUPLED,
            base_product=self.base_product,
            created_by=self.user
        )
        self.transformation = Transformation.objects.create(service_fee=0, created_by=self.user)
        self.transformation_item = TransformationItem.objects.create(
            transformation=self.transformation,
            source_product=self.base_product,
            target_product=self.coupled_product,
            engine_number="ENG-001",
            chassis_number="CHA-001",
            status=TransformationItem.Status.AVAILABLE,
            created_by=self.user
        )

        # Create Customer
        self.customer = Customer.objects.create(full_name="Test Customer", phone="1234567890", created_by=self.user)
        # Deposit Account is created by signal
        self.deposit_account = DepositAccount.objects.get(customer=self.customer)
        
        # Fund Deposit Account
        Transaction.objects.create(
            account=self.deposit_account,
            transaction_type=Transaction.TransactionType.DEPOSIT,
            amount=Decimal("100000.00"),
            created_by=self.user
        )

        # Create Agreement
        self.agreement = PurchaseAgreement.objects.create(account=self.deposit_account, created_by=self.user)
        self.line_item = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=10,
            price_per_unit=Decimal("10000.00"),
            created_by=self.user
        )

    def test_record_sale_page_loads(self):
        url = reverse('record_sale')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'customers/sales/record_sale.html')

    def test_record_normal_sale_valid(self):
        url = reverse('record_sale')
        data = {
            'customer': self.customer.pk,
            'payment_method': Sale.PaymentMethod.CASH,
            'boxed-TOTAL_FORMS': '1',
            'boxed-INITIAL_FORMS': '0',
            'boxed-MIN_NUM_FORMS': '0',
            'boxed-MAX_NUM_FORMS': '1000',
            'boxed-0-product': self.product.pk,
            'boxed-0-quantity': 2,
            'boxed-0-price': 12000,
            
            'coupled-TOTAL_FORMS': '1',
            'coupled-INITIAL_FORMS': '0', 
            'coupled-MIN_NUM_FORMS': '0',
            'coupled-MAX_NUM_FORMS': '1000',
            'coupled-0-transformation_item': '', # Empty for this test
            'coupled-0-price': '',
        }
        
        response = self.client.post(url, data)
        
        if response.status_code != 302:
             print(response.context['form'].errors)
             print(response.context['boxed_formset'].errors)
        
        self.assertRedirects(response, reverse('sales'))
        
        self.assertEqual(Sale.objects.count(), 1)
        sale = Sale.objects.first()
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.CASH)
        
        self.assertEqual(BoxedSale.objects.count(), 1)
        boxed_sale = BoxedSale.objects.first()
        self.assertEqual(boxed_sale.sale, sale)
        self.assertEqual(boxed_sale.quantity, 2)
        
        # Verify Inventory reduced
        self.product.inventory.refresh_from_db()
        self.assertEqual(self.product.inventory.quantity, 98)

    def test_record_agreement_sale_valid(self):
        url = reverse('record_sale')
        data = {
            'customer': self.customer.pk,
            'payment_method': Sale.PaymentMethod.FROM_DEPOSIT,
            'agreement': self.agreement.pk,
            
            'boxed-TOTAL_FORMS': '1',
            'boxed-INITIAL_FORMS': '0',
            'boxed-MIN_NUM_FORMS': '0',
            'boxed-MAX_NUM_FORMS': '1000',
            'boxed-0-product': self.product.pk,
            'boxed-0-quantity': 5,
            'boxed-0-price': 10000, # Matches agreement price
            'boxed-0-agreement_line_item': self.line_item.pk, # Should bind to line item if logic allows general form to do so. 
            # Note: The form I built allows manual selection, usually agreement sales are strict.
            # My current implementation of `record_sale` generic interface allows user to pick items.
            # However, for `From Deposit`, we usually strictly link items. 
            # Let's verify that the view logic binds them or if the formset handles it.
            # Looking at `BoxedSaleForm`, it has `agreement_line_item`.
            # If I populate `agreement_line_item`, it saves it.
            
            'coupled-TOTAL_FORMS': '0',
            'coupled-INITIAL_FORMS': '0',
            'coupled-MIN_NUM_FORMS': '0',
            'coupled-MAX_NUM_FORMS': '1000',
        }
        
        response = self.client.post(url, data)
        self.assertRedirects(response, reverse('sales'))
        
        sale = Sale.objects.first()
        self.assertEqual(sale.agreement, self.agreement)
        self.assertEqual(sale.payment_method, Sale.PaymentMethod.FROM_DEPOSIT)
        
        boxed_sale = BoxedSale.objects.first()
        self.assertEqual(boxed_sale.agreement_line_item, self.line_item)
        
    def test_record_sale_from_deposit_no_agreement_fails(self):
        url = reverse('record_sale')
        data = {
            'customer': self.customer.pk,
            'payment_method': Sale.PaymentMethod.FROM_DEPOSIT,
            'agreement': '', # Missing
            
            'boxed-TOTAL_FORMS': '0',
            'boxed-INITIAL_FORMS': '0', 
            'boxed-MIN_NUM_FORMS': '0',
            'boxed-MAX_NUM_FORMS': '1000',
            
            'coupled-TOTAL_FORMS': '0',
            'coupled-INITIAL_FORMS': '0',
            'coupled-MIN_NUM_FORMS': '0',
            'coupled-MAX_NUM_FORMS': '1000',
        }
        
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200) # Re-renders
        form = response.context['form']
        self.assertIn('agreement', form.errors)
        self.assertIn('Agreement is required when paying from deposit.', form.errors['agreement'])

    def test_load_customer_agreements(self):
        url = reverse('ajax_load_customer_agreements')
        response = self.client.get(url, {'customer': self.customer.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(self.agreement))
        
        # Test with no customer
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200) 
