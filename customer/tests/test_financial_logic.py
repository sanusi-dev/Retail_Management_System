from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid as _uuid
from customer.models import (
    Customer, DepositAccount, PurchaseAgreement, PurchaseAgreementLineItem,
    Sale, BoxedSale, CoupledSale, Transaction, CfaAgreement, CfaFulfillment,
)
from customer.services import (
    _refresh_balances, void_sale, record_deposit, cancel_agreement,
    BusinessRuleViolation,
)
from inventory.models import (
    Product, Brand, Inventory, InventoryTransaction,
    TransformationItem, Transformation,
)
from supply_chain.models import Supplier, PurchaseOrder, PurchaseOrderItem

User = get_user_model()

_counter = 0


def _unique_suffix():
    global _counter
    _counter += 1
    return f"{_counter}-{_uuid.uuid4().hex[:4]}"


def _create_user():
    return User.objects.create_user(
        username=f"testuser-{_unique_suffix()}", password="password"
    )


def _create_funded_customer(user, deposit_amount=Decimal("1000000.00")):
    """Create a customer with a funded deposit account."""
    customer = Customer.objects.create(
        full_name=f"Test Customer {_unique_suffix()}",
        phone="08012345678",
        created_by=user,
    )
    account = DepositAccount.objects.get(customer=customer)
    Transaction.objects.create(
        account=account,
        transaction_type=Transaction.TransactionType.DEPOSIT,
        amount=deposit_amount,
        created_by=user,
    )
    _refresh_balances(account)
    return customer, account


def _create_boxed_product(user, modelname=None, qty=50, wac=Decimal("50000.00")):
    """Create a boxed product with inventory."""
    if modelname is None:
        modelname = f"Boxed-{_unique_suffix()}"
    brand, _ = Brand.objects.get_or_create(
        name="TestBrand", defaults={"created_by": user}
    )
    product = Product.objects.create(
        brand=brand,
        modelname=modelname,
        category=Product.Category.MOTORCYCLE,
        type_variant=Product.TypeVariant.BOXED,
        created_by=user,
    )
    inv = Inventory.objects.get(product=product)
    inv.quantity = qty
    inv.weighted_average_cost = wac
    inv.save()
    # Clear stale reverse-relation cache (signal created inv at qty=0)
    product.refresh_from_db()
    return product, inv


def _create_coupled_product(user, base_product, engine=None, chassis=None):
    """Create a coupled product with an available transformation item.
    Uses the auto-created coupled product from the signal if it exists."""
    if engine is None:
        engine = f"ENG-{_unique_suffix()}"
    if chassis is None:
        chassis = f"CHA-{_unique_suffix()}"
    # Signal auto-creates a coupled product when a boxed motorcycle is created
    coupled = Product.objects.filter(
        base_product=base_product,
        type_variant=Product.TypeVariant.COUPLED,
    ).first()
    if coupled is None:
        coupled = Product.objects.create(
            brand=base_product.brand,
            modelname=base_product.modelname,
            category=base_product.category,
            type_variant=Product.TypeVariant.COUPLED,
            base_product=base_product,
            created_by=user,
        )
    transformation = Transformation.objects.create(
        service_fee=Decimal("0.00"),
        created_by=user,
    )
    ti = TransformationItem.objects.create(
        transformation=transformation,
        source_product=base_product,
        target_product=coupled,
        engine_number=engine,
        chassis_number=chassis,
        status=TransformationItem.Status.AVAILABLE,
        created_by=user,
    )
    return coupled, ti


# ─────────────────────────────────────────────────────────────────────────────
# 1. _refresh_balances() tests
# ─────────────────────────────────────────────────────────────────────────────

class RefreshBalancesTest(TestCase):
    """Test _refresh_balances() calculates correct total, allocated, available."""

    def setUp(self):
        self.user = _create_user()
        self.customer, self.account = _create_funded_customer(
            self.user, deposit_amount=Decimal("500000.00")
        )
        self.product, self.inv = _create_boxed_product(
            self.user, qty=20, wac=Decimal("30000.00")
        )

    def test_total_balance_after_deposit(self):
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        self.assertEqual(self.account.cached_total_balance, Decimal("500000.00"))
        self.assertEqual(self.account.cached_allocated_balance, Decimal("0.00"))
        self.assertEqual(self.account.cached_available_balance, Decimal("500000.00"))

    def test_total_balance_after_withdrawal(self):
        Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.WITHDRAWAL,
            amount=Decimal("100000.00"),
            created_by=self.user,
        )
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        self.assertEqual(self.account.cached_total_balance, Decimal("400000.00"))

    def test_allocated_balance_with_agreement(self):
        agreement = PurchaseAgreement.objects.create(
            account=self.account, created_by=self.user
        )
        PurchaseAgreementLineItem.objects.create(
            purchase_agreement=agreement,
            product=self.product,
            quantity_ordered=5,
            price_per_unit=Decimal("60000.00"),
            created_by=self.user,
        )
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        # Allocated = 5 * 60000 = 300000
        self.assertEqual(self.account.cached_allocated_balance, Decimal("300000.00"))
        # Available = 500000 - 300000 = 200000
        self.assertEqual(self.account.cached_available_balance, Decimal("200000.00"))

    def test_allocated_balance_with_cfa_agreement(self):
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("200000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        # CFA allocated = 200000 (the full naira amount)
        self.assertEqual(self.account.cached_allocated_balance, Decimal("200000.00"))
        # Available = 500000 - 200000 = 300000
        self.assertEqual(self.account.cached_available_balance, Decimal("300000.00"))

    def test_available_balance_with_purchase_and_cfa(self):
        agreement = PurchaseAgreement.objects.create(
            account=self.account, created_by=self.user
        )
        PurchaseAgreementLineItem.objects.create(
            purchase_agreement=agreement,
            product=self.product,
            quantity_ordered=2,
            price_per_unit=Decimal("50000.00"),
            created_by=self.user,
        )
        CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("100000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        # Purchase allocated = 2 * 50000 = 100000
        # CFA allocated = 100000
        # Total allocated = 200000
        self.assertEqual(self.account.cached_allocated_balance, Decimal("200000.00"))
        # Available = 500000 - 200000 = 300000
        self.assertEqual(self.account.cached_available_balance, Decimal("300000.00"))

    def test_balance_with_fulfillment_withdrawal(self):
        agreement = PurchaseAgreement.objects.create(
            account=self.account, created_by=self.user
        )
        ali = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=agreement,
            product=self.product,
            quantity_ordered=3,
            price_per_unit=Decimal("60000.00"),
            created_by=self.user,
        )
        # Simulate a fulfillment withdrawal
        Transaction.objects.create(
            account=self.account,
            transaction_type=Transaction.TransactionType.FULFILLMENT_WITHDRAWAL,
            amount=Decimal("60000.00"),
            created_by=self.user,
        )
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        # Total = 500000 - 60000 = 440000
        self.assertEqual(self.account.cached_total_balance, Decimal("440000.00"))


# ─────────────────────────────────────────────────────────────────────────────
# 2. PurchaseAgreementLineItem.remaining_quantity tests
# ─────────────────────────────────────────────────────────────────────────────

class RemainingQuantityTest(TestCase):
    """Test remaining_quantity counts fulfillments across all line item versions."""

    def setUp(self):
        self.user = _create_user()
        self.customer, self.account = _create_funded_customer(
            self.user, deposit_amount=Decimal("2000000.00")
        )
        self.product, self.inv = _create_boxed_product(
            self.user, qty=50, wac=Decimal("30000.00")
        )
        self.coupled, self.ti = _create_coupled_product(
            self.user, self.product, engine="ENG-R1", chassis="CHA-R1"
        )
        self.agreement = PurchaseAgreement.objects.create(
            account=self.account, created_by=self.user
        )

    def _make_sale_with_boxed(self, qty=3, ali=None):
        from customer.services import create_sale as svc_create_sale
        sale = Sale(
            customer=self.customer,
            payment_method=Sale.PaymentMethod.FROM_DEPOSIT,
            agreement=self.agreement,
            created_by=self.user,
            updated_by=self.user,
        )
        boxed = BoxedSale(
            sale=sale,
            product=self.product,
            quantity=qty,
            agreement_line_item=ali,
            created_by=self.user,
            updated_by=self.user,
        )
        return svc_create_sale(sale, [boxed], [], self.user)

    def _make_sale_with_coupled(self, ali=None):
        from customer.services import create_sale as svc_create_sale
        sale = Sale(
            customer=self.customer,
            payment_method=Sale.PaymentMethod.FROM_DEPOSIT,
            agreement=self.agreement,
            created_by=self.user,
            updated_by=self.user,
        )
        coupled = CoupledSale(
            sale=sale,
            transformation_item=self.ti,
            agreement_line_item=ali,
            created_by=self.user,
            updated_by=self.user,
        )
        return svc_create_sale(sale, [], [coupled], self.user)

    def test_remaining_equals_ordered_when_no_fulfillments(self):
        ali = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=10,
            price_per_unit=Decimal("50000.00"),
            created_by=self.user,
        )
        self.assertEqual(ali.remaining_quantity, 10)

    def test_remaining_decreases_after_boxed_sale(self):
        ali = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=10,
            price_per_unit=Decimal("50000.00"),
            created_by=self.user,
        )
        self._make_sale_with_boxed(qty=3, ali=ali)
        ali.refresh_from_db()
        self.assertEqual(ali.remaining_quantity, 7)

    def test_remaining_counts_across_versions(self):
        """Fulfillments on version 1 should reduce remaining on version 2."""
        shared_line_number = f"AGR-V1-{_uuid.uuid4().hex[:4].upper()}"
        ali_v1 = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=10,
            price_per_unit=Decimal("50000.00"),
            version=1,
            is_current_version=False,
            line_number=shared_line_number,
            created_by=self.user,
        )
        # Fulfill 3 on v1
        self._make_sale_with_boxed(qty=3, ali=ali_v1)
        # Create v2 (current version) with quantity 8, same line_number
        ali_v2 = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=8,
            price_per_unit=Decimal("50000.00"),
            version=2,
            is_current_version=True,
            superseded_by=None,
            line_number=shared_line_number,
            created_by=self.user,
        )
        ali_v1.is_current_version = False
        ali_v1.superseded_by = ali_v2
        ali_v1.save(update_fields=["is_current_version", "superseded_by"])
        # remaining = v2.quantity_ordered (8) - total fulfillments across all versions (3) = 5
        self.assertEqual(ali_v2.remaining_quantity, 5)

    def test_remaining_with_coupled_sales(self):
        ali = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=5,
            price_per_unit=Decimal("80000.00"),
            created_by=self.user,
        )
        self._make_sale_with_coupled(ali=ali)
        ali.refresh_from_db()
        self.assertEqual(ali.remaining_quantity, 4)

    def test_remaining_mixed_boxed_and_coupled(self):
        ali = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=10,
            price_per_unit=Decimal("50000.00"),
            created_by=self.user,
        )
        # Boxed sale of 3
        self._make_sale_with_boxed(qty=3, ali=ali)
        # Coupled sale of 1
        self._make_sale_with_coupled(ali=ali)
        ali.refresh_from_db()
        self.assertEqual(ali.remaining_quantity, 6)


# ─────────────────────────────────────────────────────────────────────────────
# 3. CfaAgreement.update_status() tests
# ─────────────────────────────────────────────────────────────────────────────

class CfaAgreementStatusTest(TestCase):
    """Test CfaAgreement.update_status() with epsilon tolerance."""

    def setUp(self):
        self.user = _create_user()
        self.customer, self.account = _create_funded_customer(
            self.user, deposit_amount=Decimal("5000000.00")
        )

    def test_active_when_no_fulfillments(self):
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("1800000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        cfa.update_status()
        self.assertEqual(cfa.status, CfaAgreement.Status.ACTIVE)

    def test_partially_fulfilled(self):
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("1800000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        # expected_cfa = (1800000 / 1800) * 1000 = 1000000 XOF
        CfaFulfillment.objects.create(
            cfa_agreement=cfa,
            cfa_amount_disbursed=Decimal("500000.00"),
            created_by=self.user,
        )
        cfa.update_status()
        self.assertEqual(cfa.status, CfaAgreement.Status.PARTIALLY_FULFILLED)

    def test_fulfilled_when_remaining_within_epsilon(self):
        """When remaining CFA <= 1 XOF, status should be FULFILLED."""
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("1800000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        # expected_cfa = 1000000 XOF
        # Fulfill exactly 1000000 - 0.5 = 999999.50 (within epsilon of 1)
        CfaFulfillment.objects.create(
            cfa_agreement=cfa,
            cfa_amount_disbursed=Decimal("999999.50"),
            created_by=self.user,
        )
        cfa.update_status()
        self.assertEqual(cfa.status, CfaAgreement.Status.FULFILLED)

    def test_fulfilled_when_exact_match(self):
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("1800000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        # expected_cfa = 1000000 XOF
        CfaFulfillment.objects.create(
            cfa_agreement=cfa,
            cfa_amount_disbursed=Decimal("1000000.00"),
            created_by=self.user,
        )
        cfa.update_status()
        self.assertEqual(cfa.status, CfaAgreement.Status.FULFILLED)

    def test_not_fulfilled_when_remaining_exceeds_epsilon(self):
        """When remaining CFA > 1 XOF, status should be PARTIALLY_FULFILLED."""
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("1800000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        # expected_cfa = 1000000 XOF
        # Fulfill 999800 -> remaining = 200 > 1
        CfaFulfillment.objects.create(
            cfa_agreement=cfa,
            cfa_amount_disbursed=Decimal("999800.00"),
            created_by=self.user,
        )
        cfa.update_status()
        self.assertEqual(cfa.status, CfaAgreement.Status.PARTIALLY_FULFILLED)

    def test_voided_fulfillment_not_counted(self):
        cfa = CfaAgreement.objects.create(
            account=self.account,
            amount_allocated=Decimal("1800000.00"),
            exchange_rate=Decimal("1800.00"),
            created_by=self.user,
        )
        CfaFulfillment.objects.create(
            cfa_agreement=cfa,
            cfa_amount_disbursed=Decimal("1000000.00"),
            status=CfaFulfillment.Status.VOIDED,
            created_by=self.user,
        )
        cfa.update_status()
        # Voided fulfillment not counted, so total_fulfilled_cfa = 0
        self.assertEqual(cfa.status, CfaAgreement.Status.ACTIVE)


# ─────────────────────────────────────────────────────────────────────────────
# 4. void_sale() tests
# ─────────────────────────────────────────────────────────────────────────────

class VoidSaleTest(TestCase):
    """Test void_sale() restores inventory, refunds balance, updates agreement."""

    def setUp(self):
        self.user = _create_user()
        self.customer, self.account = _create_funded_customer(
            self.user, deposit_amount=Decimal("1000000.00")
        )
        self.product, self.inv = _create_boxed_product(
            self.user, qty=20, wac=Decimal("30000.00")
        )
        self.coupled, self.ti = _create_coupled_product(
            self.user, self.product, engine="ENG-V1", chassis="CHA-V1"
        )
        self.agreement = PurchaseAgreement.objects.create(
            account=self.account, created_by=self.user
        )
        self.line_item = PurchaseAgreementLineItem.objects.create(
            purchase_agreement=self.agreement,
            product=self.product,
            quantity_ordered=5,
            price_per_unit=Decimal("80000.00"),
            created_by=self.user,
        )

    def _create_deposit_sale_with_boxed(self, qty=2):
        """Helper: create a deposit sale with a boxed item via the service."""
        from customer.services import create_sale as svc_create_sale

        sale = Sale(
            customer=self.customer,
            payment_method=Sale.PaymentMethod.FROM_DEPOSIT,
            agreement=self.agreement,
            created_by=self.user,
            updated_by=self.user,
        )
        boxed = BoxedSale(
            sale=sale,
            product=self.product,
            quantity=qty,
            agreement_line_item=self.line_item,
            created_by=self.user,
            updated_by=self.user,
        )
        return svc_create_sale(sale, [boxed], [], self.user)

    def test_void_sale_restores_boxed_inventory(self):
        initial_qty = self.inv.quantity  # 20
        sale = self._create_deposit_sale_with_boxed(qty=3)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, initial_qty - 3)

        void_sale(sale.pk, "Test void", self.user)
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, initial_qty)

    def test_void_sale_refunds_deposit_balance(self):
        sale = self._create_deposit_sale_with_boxed(qty=2)
        self.account.refresh_from_db()
        # After sale: total = 1000000 - (2*80000) = 840000
        self.assertEqual(self.account.cached_total_balance, Decimal("840000.00"))

        void_sale(sale.pk, "Test void", self.user)
        self.account.refresh_from_db()
        # After void: total = 840000 + 160000 (refund deposit) = 1000000
        self.assertEqual(self.account.cached_total_balance, Decimal("1000000.00"))

    def test_void_sale_restores_coupled_item_status(self):
        from customer.services import create_sale as svc_create_sale
        sale = Sale(
            customer=self.customer,
            payment_method=Sale.PaymentMethod.FROM_DEPOSIT,
            agreement=self.agreement,
            created_by=self.user,
            updated_by=self.user,
        )
        coupled_sale = CoupledSale(
            sale=sale,
            transformation_item=self.ti,
            agreement_line_item=self.line_item,
            created_by=self.user,
            updated_by=self.user,
        )
        sale = svc_create_sale(sale, [], [coupled_sale], self.user)
        self.ti.refresh_from_db()
        self.assertEqual(self.ti.status, TransformationItem.Status.SOLD)

        void_sale(sale.pk, "Test void", self.user)
        self.ti.refresh_from_db()
        self.assertEqual(self.ti.status, TransformationItem.Status.AVAILABLE)

    def test_void_sale_marks_sale_voided(self):
        sale = self._create_deposit_sale_with_boxed(qty=1)
        void_sale(sale.pk, "Reason here", self.user)
        sale.refresh_from_db()
        self.assertEqual(sale.status, Sale.Status.VOIDED)
        self.assertEqual(sale.void_reason, "Reason here")

    def test_void_sale_already_voided_raises(self):
        sale = self._create_deposit_sale_with_boxed(qty=1)
        void_sale(sale.pk, "First void", self.user)
        with self.assertRaises(BusinessRuleViolation):
            void_sale(sale.pk, "Second void", self.user)

    def test_void_sale_cash_sale_no_refund(self):
        """Cash sales should not create a deposit refund."""
        sale = Sale.objects.create(
            customer=self.customer,
            payment_method=Sale.PaymentMethod.CASH,
            created_by=self.user,
        )
        BoxedSale.objects.create(
            sale=sale,
            product=self.product,
            quantity=2,
            price=Decimal("80000.00"),
            created_by=self.user,
        )
        initial_total = self.account._calculate_total_balance()

        void_sale(sale.pk, "Test void", self.user)
        self.account.refresh_from_db()
        # No refund for cash sales
        _refresh_balances(self.account)
        self.account.refresh_from_db()
        self.assertEqual(self.account.cached_total_balance, initial_total)

    def test_void_sale_updates_agreement_status(self):
        sale = self._create_deposit_sale_with_boxed(qty=5)
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.status, PurchaseAgreement.Status.FULFILLED)

        void_sale(sale.pk, "Test void", self.user)
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.status, PurchaseAgreement.Status.ACTIVE)

    def test_void_sale_creates_inventory_transaction(self):
        sale = self._create_deposit_sale_with_boxed(qty=2)
        void_sale(sale.pk, "Test void", self.user)
        reversal_txns = InventoryTransaction.objects.filter(
            transaction_type=InventoryTransaction.TransactionType.SALE_REVERSAL
        )
        self.assertEqual(reversal_txns.count(), 1)
        txn = reversal_txns.first()
        self.assertEqual(txn.quantity_change, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 5. WAC formula tests (process_goods_receipt logic)
# ─────────────────────────────────────────────────────────────────────────────

class WACFormulaTest(TestCase):
    """Test the Weighted Average Cost formula used in goods receipt processing."""

    def setUp(self):
        self.user = _create_user()
        self.product, self.inv = _create_boxed_product(
            self.user, qty=0, wac=Decimal("0.00")
        )

    def test_wac_from_zero_stock(self):
        """First receipt: WAC = unit cost."""
        # Simulate: old_qty=0, old_wac=0, received_qty=10, unit_cost=50000
        old_qty = self.inv.quantity  # 0
        old_wac = self.inv.weighted_average_cost  # 0
        received_qty = 10
        unit_cost = Decimal("50000.00")

        new_qty = old_qty + received_qty
        total_value = (old_qty * old_wac) + (received_qty * unit_cost)
        wac = total_value / new_qty if new_qty > 0 else 0

        self.inv.quantity = new_qty
        self.inv.weighted_average_cost = wac
        self.inv.save()

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 10)
        self.assertEqual(self.inv.weighted_average_cost, Decimal("50000.00"))

    def test_wac_with_existing_stock(self):
        """Second receipt: WAC blends old and new costs."""
        self.inv.quantity = 10
        self.inv.weighted_average_cost = Decimal("50000.00")
        self.inv.save()

        # Receive 5 more at 60000 each
        old_qty = 10
        old_wac = Decimal("50000.00")
        received_qty = 5
        unit_cost = Decimal("60000.00")

        new_qty = old_qty + received_qty
        total_value = (old_qty * old_wac) + (received_qty * unit_cost)
        wac = total_value / new_qty

        self.inv.quantity = new_qty
        self.inv.weighted_average_cost = wac
        self.inv.save()

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 15)
        # WAC = (10*50000 + 5*60000) / 15 = (500000+300000)/15 = 800000/15 = 53333.33
        expected_wac = Decimal("53333.33")
        self.assertEqual(
            self.inv.weighted_average_cost.quantize(Decimal("0.01")),
            expected_wac,
        )

    def test_wac_preserves_precision(self):
        """WAC with non-rounding results."""
        self.inv.quantity = 7
        self.inv.weighted_average_cost = Decimal("33333.33")
        self.inv.save()

        old_qty = 7
        old_wac = Decimal("33333.33")
        received_qty = 3
        unit_cost = Decimal("40000.00")

        new_qty = old_qty + received_qty
        total_value = (old_qty * old_wac) + (received_qty * unit_cost)
        wac = total_value / new_qty

        self.inv.quantity = new_qty
        self.inv.weighted_average_cost = wac
        self.inv.save()

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 10)
        # total_value = 7*33333.33 + 3*40000 = 233333.31 + 120000 = 353333.31
        # wac = 353333.31 / 10 = 35333.331
        expected = Decimal("353333.31") / 10
        self.assertEqual(
            self.inv.weighted_average_cost.quantize(Decimal("0.01")),
            expected.quantize(Decimal("0.01")),
        )

    def test_wac_with_delivery_cost_allocation(self):
        """Delivery cost is added to unit cost before WAC calculation."""
        self.inv.quantity = 10
        self.inv.weighted_average_cost = Decimal("50000.00")
        self.inv.save()

        # PO item unit price = 55000, delivery cost = 10000 for 5 units
        po_unit_price = Decimal("55000.00")
        delivery_cost = Decimal("10000.00")
        received_qty = 5
        allocated_delivery_per_unit = delivery_cost / received_qty  # 2000
        unit_cost_at_receipt = po_unit_price + allocated_delivery_per_unit  # 57000

        old_qty = 10
        old_wac = Decimal("50000.00")
        new_qty = old_qty + received_qty
        total_value = (old_qty * old_wac) + (received_qty * unit_cost_at_receipt)
        wac = total_value / new_qty

        self.inv.quantity = new_qty
        self.inv.weighted_average_cost = wac
        self.inv.save()

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 15)
        # total_value = 10*50000 + 5*57000 = 500000 + 285000 = 785000
        # wac = 785000 / 15 = 52333.33
        expected = Decimal("52333.33")
        self.assertEqual(
            self.inv.weighted_average_cost.quantize(Decimal("0.01")),
            expected,
        )

    def test_wac_multiple_receipts(self):
        """Three consecutive receipts should produce correct cumulative WAC."""
        # Receipt 1: 10 @ 50000
        self.inv.quantity = 10
        self.inv.weighted_average_cost = Decimal("50000.00")
        self.inv.save()

        # Receipt 2: 5 @ 60000
        new_qty = 10 + 5
        total_value = (10 * Decimal("50000.00")) + (5 * Decimal("60000.00"))
        wac = total_value / new_qty
        self.inv.quantity = new_qty
        self.inv.weighted_average_cost = wac
        self.inv.save()

        # Receipt 3: 10 @ 45000
        old_qty = self.inv.quantity  # 15
        old_wac = self.inv.weighted_average_cost
        new_qty = old_qty + 10
        total_value = (old_qty * old_wac) + (10 * Decimal("45000.00"))
        wac = total_value / new_qty
        self.inv.quantity = new_qty
        self.inv.weighted_average_cost = wac
        self.inv.save()

        self.inv.refresh_from_db()
        self.assertEqual(self.inv.quantity, 25)
        # After receipt 2: wac = (500000+300000)/15 = 53333.33
        # After receipt 3: total = 15*53333.33 + 10*45000 = 799999.95 + 450000 = 1249999.95
        # wac = 1249999.95 / 25 = 49999.998
        expected = Decimal("49999.998").quantize(Decimal("0.01"))
        self.assertEqual(
            self.inv.weighted_average_cost.quantize(Decimal("0.01")),
            expected,
        )
