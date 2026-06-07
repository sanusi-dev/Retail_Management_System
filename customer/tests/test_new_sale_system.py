from django.test import TestCase, Client
from django.urls import reverse
from account.models import CustomUser
from customer.models import Customer, DepositAccount, PurchaseAgreement, PurchaseAgreementLineItem
from inventory.models import Brand, Product, Inventory, TransformationItem


class NewSaleSystemTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testsale", password="testpass"
        )
        self.client.force_login(self.user)

        self.customer = Customer.objects.create(
            full_name="Test Customer",
            created_by=self.user,
            updated_by=self.user,
        )
        # DepositAccount is auto-created by signal
        self.account = self.customer.deposit_account

        self.brand = Brand.objects.create(name="TestBrand")
        self.boxed_product = Product.objects.create(
            brand=self.brand,
            modelname="BoxedBike",
            category=Product.Category.MOTORCYCLE,
            type_variant=Product.TypeVariant.BOXED,
            created_by=self.user,
            updated_by=self.user,
        )
        self.inventory = self.boxed_product.inventory
        self.inventory.quantity = 10
        self.inventory.weighted_average_cost = 50000
        self.inventory.save()

    def test_create_normal_sale_page_loads(self):
        resp = self.client.get(reverse("create_normal_sale"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Create Normal Sale")

    def test_search_customers_for_sale(self):
        resp = self.client.get(
            reverse("search_customers_for_sale") + "?new_customer_name=Test"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test Customer")

    def test_create_normal_sale_with_existing_customer(self):
        data = {
            "customer": str(self.customer.pk),
            "payment_method": "cash",
            "boxed-TOTAL_FORMS": "1",
            "boxed-INITIAL_FORMS": "0",
            "boxed-MIN_NUM_FORMS": "0",
            "boxed-MAX_NUM_FORMS": "1000",
            "boxed-0-product": str(self.boxed_product.pk),
            "boxed-0-quantity": "2",
            "boxed-0-price": "75000",
            "coupled-TOTAL_FORMS": "0",
            "coupled-INITIAL_FORMS": "0",
            "coupled-MIN_NUM_FORMS": "0",
            "coupled-MAX_NUM_FORMS": "1000",
        }
        resp = self.client.post(reverse("create_normal_sale"), data)
        self.assertEqual(resp.status_code, 302)  # redirect to sales list

    def test_create_normal_sale_requires_customer(self):
        data = {
            "customer": "",
            "payment_method": "cash",
            "boxed-TOTAL_FORMS": "0",
            "boxed-INITIAL_FORMS": "0",
            "boxed-MIN_NUM_FORMS": "0",
            "boxed-MAX_NUM_FORMS": "1000",
            "coupled-TOTAL_FORMS": "0",
            "coupled-INITIAL_FORMS": "0",
            "coupled-MIN_NUM_FORMS": "0",
            "coupled-MAX_NUM_FORMS": "1000",
        }
        resp = self.client.post(reverse("create_normal_sale"), data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "This field is required")

    def test_create_normal_sale_stock_validation(self):
        data = {
            "customer": str(self.customer.pk),
            "payment_method": "cash",
            "boxed-TOTAL_FORMS": "1",
            "boxed-INITIAL_FORMS": "0",
            "boxed-MIN_NUM_FORMS": "0",
            "boxed-MAX_NUM_FORMS": "1000",
            "boxed-0-product": str(self.boxed_product.pk),
            "boxed-0-quantity": "999",  # exceeds stock
            "boxed-0-price": "75000",
            "coupled-TOTAL_FORMS": "0",
            "coupled-INITIAL_FORMS": "0",
            "coupled-MIN_NUM_FORMS": "0",
            "coupled-MAX_NUM_FORMS": "1000",
        }
        resp = self.client.post(reverse("create_normal_sale"), data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Insufficient stock")

    def test_fulfill_agreement_page_loads(self):
        agreement = PurchaseAgreement.objects.create(
            account=self.account,
            created_by=self.user,
            updated_by=self.user,
        )
        line = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=agreement,
            product=self.boxed_product,
            quantity_ordered=5,
            price_per_unit=60000,
            created_by=self.user,
            updated_by=self.user,
        )
        url = reverse(
            "fulfill_agreement",
            args=[self.customer.pk, agreement.pk],
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Fulfil Agreement")
        self.assertContains(resp, line.product.modelname.title())

    def test_fulfill_agreement_exceeds_quantity(self):
        agreement = PurchaseAgreement.objects.create(
            account=self.account,
            created_by=self.user,
            updated_by=self.user,
        )
        line = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=agreement,
            product=self.boxed_product,
            quantity_ordered=5,
            price_per_unit=60000,
            created_by=self.user,
            updated_by=self.user,
        )
        url = reverse(
            "fulfill_agreement",
            args=[self.customer.pk, agreement.pk],
        )
        data = {
            "fulfill-TOTAL_FORMS": "1",
            "fulfill-INITIAL_FORMS": "0",
            "fulfill-MIN_NUM_FORMS": "0",
            "fulfill-MAX_NUM_FORMS": "1000",
            "fulfill-0-line_item": str(line.pk),
            "fulfill-0-product": str(self.boxed_product.pk),
            "fulfill-0-price": "60000",
            "fulfill-0-quantity": "10",  # exceeds remaining 5
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Cannot fulfil more than the remaining quantity")

    def test_fulfill_agreement_success(self):
        agreement = PurchaseAgreement.objects.create(
            account=self.account,
            created_by=self.user,
            updated_by=self.user,
        )
        line = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=agreement,
            product=self.boxed_product,
            quantity_ordered=5,
            price_per_unit=60000,
            created_by=self.user,
            updated_by=self.user,
        )
        url = reverse(
            "fulfill_agreement",
            args=[self.customer.pk, agreement.pk],
        )
        data = {
            "fulfill-TOTAL_FORMS": "1",
            "fulfill-INITIAL_FORMS": "0",
            "fulfill-MIN_NUM_FORMS": "0",
            "fulfill-MAX_NUM_FORMS": "1000",
            "fulfill-0-line_item": str(line.pk),
            "fulfill-0-product": str(self.boxed_product.pk),
            "fulfill-0-price": "60000",
            "fulfill-0-quantity": "3",
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)  # redirect to customer detail
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity, 7)  # 10 - 3
