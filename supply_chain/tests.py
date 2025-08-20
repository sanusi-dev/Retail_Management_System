import uuid
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Supplier, PurchaseOrder, PurchaseOrderItem
from inventory.models import Brand, Product

CustomUser = get_user_model()


class PurchaseOrderViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            username="testuser", password="password123"
        )
        cls.brand = Brand.objects.create(name="Test Brand", created_by=cls.user)
        cls.supplier = Supplier.objects.create(
            name="Test Supplier Inc.",
            phone="555-123-4567",
            email="contact@testsupplier.com",
            created_by=cls.user,
        )
        cls.product1 = Product.objects.create(
            sku="WIDGET-A-001",
            brand=cls.brand,
            modelname="Standard Widget",
            category=Product.Category.SPARE_PART,
            created_by=cls.user,
        )
        cls.product2 = Product.objects.create(
            sku="GIZMO-B-002",
            brand=cls.brand,
            modelname="Fancy Gizmo",
            category=Product.Category.SPARE_PART,
            created_by=cls.user,
        )
        cls.product3 = Product.objects.create(
            sku="THING-C-003",
            brand=cls.brand,
            modelname="Simple Thing",
            category=Product.Category.SPARE_PART,
            created_by=cls.user,
        )

        cls.po = PurchaseOrder.objects.create(
            supplier=cls.supplier, created_by=cls.user
        )
        cls.po_item1 = PurchaseOrderItem.objects.create(
            purchase_order=cls.po,
            product=cls.product1,
            ordered_quantity=10,
            unit_price_at_order=15.00,
            created_by=cls.user,
        )
        cls.po_item2 = PurchaseOrderItem.objects.create(
            purchase_order=cls.po,
            product=cls.product2,
            ordered_quantity=5,
            unit_price_at_order=100.00,
            created_by=cls.user,
        )

        cls.add_po_url = reverse("add_po")
        cls.edit_po_url = reverse("edit_po", args=[cls.po.pk])
        cls.htmx_add_item_url = reverse("htmx_add_po_item")

    def setUp(self):
        self.client = Client()
        self.client.login(username="testuser", password="password123")

    def test_add_purchase_order_page_get_request(self):
        response = self.client.get(self.add_po_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "supply_chain/po/form.html")
        self.assertEqual(len(response.context["item_formset"]), 2)

    def test_edit_purchase_order_page_get_request(self):
        response = self.client.get(self.edit_po_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "supply_chain/po/form.html")
        self.assertEqual(len(response.context["item_formset"]), 4)
        self.assertEqual(response.context["item_formset"][0].instance, self.po_item2)
        self.assertEqual(response.context["item_formset"][1].instance, self.po_item1)

    def test_htmx_add_item_view_returns_correct_html(self):
        next_form_index = 2
        headers = {"HTTP_HX_REQUEST": "true"}
        response = self.client.get(
            f"{self.htmx_add_item_url}?index={next_form_index}", **headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "supply_chain/po/partials/po_item_form_row.html"
        )
        self.assertContains(response, f'name="items-{next_form_index}-product"')
        self.assertContains(
            response, f'name="items-{next_form_index}-ordered_quantity"'
        )
        self.assertContains(response, 'class="remove-form-row')
        self.assertNotContains(response, f'name="items-{next_form_index}-DELETE"')

    def test_create_purchase_order_with_items_success(self):
        form_data = {
            "supplier": self.supplier.pk,
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-product": self.product1.pk,
            "items-0-ordered_quantity": 5,
            "items-0-unit_price_at_order": 1001.00,
            "items-1-product": self.product2.pk,
            "items-1-ordered_quantity": 20,
            "items-1-unit_price_at_order": 1002.00,
        }
        response = self.client.post(self.add_po_url, data=form_data)
        self.assertRedirects(response, reverse("purchases"), status_code=302)
        self.assertEqual(PurchaseOrder.objects.count(), 2)
        self.assertEqual(PurchaseOrderItem.objects.count(), 4)
        new_po = PurchaseOrder.objects.latest("created_at")
        self.assertEqual(new_po.supplier, self.supplier)
        self.assertEqual(new_po.po_items.count(), 2)

    def test_update_po_add_and_delete_items(self):
        form_data = {
            "supplier": self.supplier.pk,
            "items-TOTAL_FORMS": "3",
            "items-INITIAL_FORMS": "2",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            # Use 'po_item_id' instead of 'id'
            "items-0-po_item_id": self.po_item2.pk,
            "items-0-purchase_order": self.po.pk,
            "items-0-product": self.product2.pk,
            "items-0-ordered_quantity": 5,
            "items-0-unit_price_at_order": 1100.00,
            "items-0-DELETE": "on",
            # Use 'po_item_id' instead of 'id'
            "items-1-po_item_id": self.po_item1.pk,
            "items-1-purchase_order": self.po.pk,
            "items-1-product": self.product1.pk,
            "items-1-ordered_quantity": 10,
            "items-1-unit_price_at_order": 1500.00,
            "items-2-product": self.product3.pk,
            "items-2-ordered_quantity": 50,
            "items-2-unit_price_at_order": 1001.00,
        }
        response = self.client.post(self.edit_po_url, data=form_data)
        self.assertRedirects(response, reverse("purchases"), status_code=302)
        self.po.refresh_from_db()
        self.assertEqual(self.po.po_items.count(), 2)
        self.assertFalse(PurchaseOrderItem.objects.filter(pk=self.po_item2.pk).exists())
        self.assertTrue(self.po.po_items.filter(product=self.product3).exists())
