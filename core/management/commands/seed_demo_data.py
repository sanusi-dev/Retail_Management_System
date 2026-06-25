import random
import string
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone

from account.models import CustomUser
from customer.models import (
    Customer, DepositAccount, Transaction, Sale, BoxedSale, CoupledSale,
    PurchaseAgreement, PurchaseAgreementLineItem,
    CfaAgreement, CfaFulfillment,
)
from customer.services import (
    record_deposit, create_sale, create_purchase_agreement,
    create_cfa_agreement, record_cfa_fulfillment,
)
from inventory.models import (
    Brand, Product, Inventory, InventoryCostLayer, InventoryTransaction,
    Transformation, TransformationItem,
)
from inventory.services import _deplete_fifo_layers, _recalculate_assembly_cost
from inventory.utils import create_inventory_transaction
from supply_chain.models import (
    Supplier, PurchaseOrder, PurchaseOrderItem, Payment,
    GoodsReceipt, GoodsReceiptItem,
)
from supply_chain.services import record_supplier_payment


now = timezone.now()


def _days_ago(days):
    return now - timedelta(days=days)


def _random_eng():
    prefix = "".join(random.choices(string.ascii_uppercase, k=2))
    digits = "".join(random.choices(string.digits, k=6))
    return f"ENG-{prefix}{digits}"


def _random_chs():
    prefix = "".join(random.choices(string.ascii_uppercase, k=2))
    digits = "".join(random.choices(string.digits, k=8))
    return f"CHS-{prefix}{digits}"


class Command(BaseCommand):
    help = (
        "Seeds realistic Nigerian motorcycle dealership demo data. "
        "Idempotent — safe to run multiple times."
    )

    def handle(self, *args, **options):
        admin_user = self._seed_users()

        self._seed_brands(admin_user)
        products = self._seed_products(admin_user)
        suppliers = self._seed_suppliers(admin_user)
        customers = self._seed_customers(admin_user)

        any_pos = PurchaseOrder.objects.exists()
        if not any_pos:
            self._seed_supply_chain(admin_user, products, suppliers)
            self._seed_transformations(admin_user, products)
            self._seed_deposits(admin_user, customers)
            self._seed_purchase_agreements(admin_user, customers, products)
            self._seed_cfa_agreements(admin_user, customers)
            self._seed_sales(admin_user, customers, products)
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  Purchase orders already exist — skipping financial activity seed."
                )
            )

        self._print_summary(customers, products, suppliers)
        self.stdout.write(self.style.SUCCESS("\nDemo data seeding complete!"))

    # ------------------------------------------------------------------
    # Phase 1 — Users
    # ------------------------------------------------------------------
    def _seed_users(self):
        admin, created = CustomUser.objects.get_or_create(
            username="admin",
            defaults={
                "is_superuser": True,
                "is_staff": True,
                "email": "admin@retailms.com",
            },
        )
        if created:
            admin.set_password("demo1234")
            admin.save()
            self.stdout.write(self.style.SUCCESS("  Created superuser: admin / demo1234"))
        else:
            self.stdout.write("  Superuser 'admin' already exists.")

        staff, created = CustomUser.objects.get_or_create(
            username="staff",
            defaults={
                "is_staff": True,
                "email": "staff@retailms.com",
            },
        )
        if created:
            staff.set_password("demo1234")
            staff.save()
            self.stdout.write(self.style.SUCCESS("  Created staff user: staff / demo1234"))
        else:
            self.stdout.write("  Staff user 'staff' already exists.")

        return admin

    # ------------------------------------------------------------------
    # Phase 2 — Brands & Products
    # ------------------------------------------------------------------
    def _seed_brands(self, user):
        for name in ["Honda", "Bajaj", "TVS", "Yamaha", "Suzuki"]:
            _, created = Brand.objects.get_or_create(
                name=name,
                defaults={"created_by": user, "updated_by": user},
            )
            if created:
                self.stdout.write(f"  Created brand: {name}")

    def _seed_products(self, user):
        self.stdout.write("  Seeding products...")
        products_info = [
            ("Honda", "CG 125", "125cc commuter motorcycle", Decimal("450000")),
            ("Bajaj", "Boxer 100", "100cc economy motorcycle", Decimal("360000")),
            ("TVS", "Star 110", "110cc commuter motorcycle", Decimal("340000")),
            ("Yamaha", "YBR 125", "125cc sport commuter", Decimal("420000")),
            ("Suzuki", "GD 110", "110cc commuter motorcycle", Decimal("350000")),
            ("Honda", "Ace 110", "110cc rugged bike", Decimal("400000")),
            ("Bajaj", "CT 100", "100cc entry level motorcycle", Decimal("330000")),
            ("TVS", "Apache 160", "160cc sport motorcycle", Decimal("520000")),
            ("Yamaha", "FZ 150", "150cc street fighter", Decimal("480000")),
            ("Suzuki", "Hayate 110", "110cc commuter", Decimal("340000")),
            ("Bajaj", "Pulsar 150", "150cc sport commuter", Decimal("500000")),
            ("Honda", "CBF 150", "150cc all-rounder", Decimal("460000")),
            ("TVS", "HLX 150", "150cc heavy-duty motorcycle", Decimal("470000")),
            ("Yamaha", "XTZ 125", "125cc dual-sport", Decimal("410000")),
            ("Suzuki", "Gixxer 150", "150cc street sport", Decimal("470000")),
        ]

        result = []
        for brand_name, modelname, description, _unit_price in products_info:
            brand = Brand.objects.get(name=brand_name)
            lookup = {
                "brand": brand,
                "modelname": modelname,
                "type_variant": Product.TypeVariant.BOXED,
            }
            product, created = Product.objects.get_or_create(
                **lookup,
                defaults={
                    "category": Product.Category.MOTORCYCLE,
                    "description": description,
                    "created_by": user,
                    "updated_by": user,
                },
            )
            if created:
                self.stdout.write(f"    Created: {brand_name} {modelname} (boxed)")
                coupled = Product.objects.filter(
                    brand=brand,
                    modelname=modelname,
                    type_variant=Product.TypeVariant.COUPLED,
                ).first()
                if coupled:
                    self.stdout.write(f"      → auto-created coupled: {coupled.sku}")
            result.append(product)
        return result

    # ------------------------------------------------------------------
    # Phase 3 — Suppliers
    # ------------------------------------------------------------------
    def _seed_suppliers(self, user):
        suppliers_info = [
            {
                "company_name": "Automatic Parts Nigeria Ltd",
                "full_name": "Alhaji Bala Mohammed",
                "phone": "08021234567",
                "address": "Plot 12, Kano Road, Kaduna",
            },
            {
                "company_name": "Lagos Motorcycle Supplies",
                "full_name": "Chief Emeka Eze",
                "phone": "08039876543",
                "address": "45 Idumota Market, Lagos Island, Lagos",
            },
            {
                "company_name": "Kano Wholesale Ventures",
                "full_name": "Alhaji Sani Abubakar",
                "phone": "08057654321",
                "address": "78 Ibrahim Taiwo Road, Kano",
            },
        ]
        suppliers = []
        for info in suppliers_info:
            sup, _ = Supplier.objects.get_or_create(
                company_name=info["company_name"],
                defaults={
                    "full_name": info["full_name"],
                    "phone": info["phone"],
                    "address": info["address"],
                    "created_by": user,
                    "updated_by": user,
                },
            )
            suppliers.append(sup)
        self.stdout.write(f"  Seeded {len(suppliers)} suppliers.")
        return suppliers

    # ------------------------------------------------------------------
    # Phase 4 — Customers
    # ------------------------------------------------------------------
    def _seed_customers(self, user):
        customers_info = [
            ("Ahmed Ibrahim", "08031112233", "No. 5 Zaria Road, Kaduna"),
            ("Chidi Okafor", "08052223344", "12 Awolowo Way, Ikeja, Lagos"),
            ("Musa Bello", "08063334455", "34 Ahmadu Bello Way, Kano"),
            ("Fatima Usman", "08074445566", "78 Sokoto Road, Kaduna"),
            ("Oluwaseun Adeyemi", "08085556677", "15 Broad Street, Lagos Island"),
            ("Ibe Okonkwo", "08096667788", "22 Zik Avenue, Enugu"),
            ("Aisha Suleiman", "08107778899", "90 Maiduguri Road, Kano"),
            ("Emeka Nwankwo", "08118889900", "55 Ogui Road, Enugu"),
            ("Zainab Abdullahi", "08129990011", "101 Waziri Ibrahim, Kaduna"),
            ("Yusuf Adamu", "08130001122", "200 Murtala Mohammed Way, Kano"),
            ("Grace Okonkwo", "08141112233", "67 Independence Layout, Enugu"),
            ("Ibrahim Tanko", "08152223344", "32 Katsina Road, Kaduna"),
        ]

        customers = []
        for full_name, phone, address in customers_info:
            customer, created = Customer.objects.get_or_create(
                full_name=full_name,
                defaults={
                    "phone": phone,
                    "address": address,
                    "created_by": user,
                    "updated_by": user,
                },
            )
            if created:
                acct = customer.deposit_account
                self.stdout.write(f"  Created: {full_name} (acct: {acct.account_number})")
            customers.append(customer)
        return customers

    # ------------------------------------------------------------------
    # Phase 5 — Supply Chain
    # ------------------------------------------------------------------
    def _seed_supply_chain(self, user, products, suppliers):
        self.stdout.write("\n  --- Supply Chain ---")

        po1 = self._create_po(
            user, suppliers[0],
            [
                (products[0], 10, Decimal("450000")),    # Honda CG 125
                (products[1], 15, Decimal("360000")),    # Bajaj Boxer 100
                (products[3], 8, Decimal("420000")),     # Yamaha YBR 125
                (products[2], 12, Decimal("340000")),    # TVS Star 110
                (products[9], 10, Decimal("340000")),    # Suzuki Hayate 110
            ],
            title="PO-1 (Automatic Parts Nigeria)",
        )

        po2 = self._create_po(
            user, suppliers[1],
            [
                (products[4], 10, Decimal("350000")),    # Suzuki GD 110
                (products[5], 8, Decimal("400000")),     # Honda Ace 110
                (products[10], 6, Decimal("500000")),    # Bajaj Pulsar 150
                (products[8], 5, Decimal("480000")),     # Yamaha FZ 150
                (products[6], 12, Decimal("330000")),    # Bajaj CT 100
            ],
            title="PO-2 (Lagos Motorcycle Supplies)",
        )

        po3 = self._create_po(
            user, suppliers[2],
            [
                (products[7], 8, Decimal("520000")),     # TVS Apache 160
                (products[14], 6, Decimal("470000")),    # Suzuki Gixxer 150
                (products[11], 7, Decimal("460000")),    # Honda CBF 150
                (products[13], 5, Decimal("410000")),    # Yamaha XTZ 125
                (products[12], 6, Decimal("470000")),    # TVS HLX 150
            ],
            title="PO-3 (Kano Wholesale Ventures)",
        )

        for po in [po1, po2, po3]:
            self._pay_and_receive(po, user)

    def _create_po(self, user, supplier, items_data, title):
        po = PurchaseOrder.objects.create(
            supplier=supplier,
            created_by=user,
            updated_by=user,
        )
        total_amount = Decimal("0.00")
        for product, qty, unit_price in items_data:
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                product=product,
                ordered_quantity=qty,
                unit_price_at_order=unit_price,
                created_by=user,
                updated_by=user,
            )
            total_amount += unit_price * qty

        self.stdout.write(f"    {title}: ₦{total_amount:,.2f} across {len(items_data)} products")
        return po

    def _pay_and_receive(self, po, user):
        total = sum(
            item.ordered_quantity * item.unit_price_at_order
            for item in po.po_items.all()
        )

        record_supplier_payment(
            po=po, amount=total, method=Payment.PaymentMethod.TRANSFER,
            user=user, remark="Full payment — seed data",
        )
        self.stdout.write(f"      Paid ₦{total:,.2f}")

        with db_transaction.atomic():
            receipt = GoodsReceipt.objects.create(
                purchase_order=po,
                received_by=user,
                delivery_cost=Decimal("0"),
                created_by=user,
                updated_by=user,
            )

            for po_item in po.po_items.select_related("product__inventory").all():
                qty = po_item.ordered_quantity
                cost = po_item.unit_price_at_order
                inventory = Inventory.objects.select_for_update().get(
                    product=po_item.product
                )
                old_qty = inventory.quantity
                old_wac = inventory.weighted_average_cost

                receipt_item = GoodsReceiptItem.objects.create(
                    goods_receipt=receipt,
                    purchase_order_item=po_item,
                    product=po_item.product,
                    received_quantity=qty,
                    unit_cost_at_receipt=cost,
                    created_by=user,
                    updated_by=user,
                )

                new_qty = old_qty + qty
                if new_qty > 0:
                    total_value = (old_qty * old_wac) + (qty * cost)
                    new_wac = total_value / new_qty
                else:
                    new_wac = Decimal("0")

                inventory.quantity = new_qty
                inventory.weighted_average_cost = new_wac
                inventory.save(
                    update_fields=["quantity", "weighted_average_cost", "updated_at"]
                )

                InventoryCostLayer.objects.create(
                    product=po_item.product,
                    quantity=qty,
                    remaining_quantity=qty,
                    unit_cost=cost,
                    goods_receipt_item=receipt_item,
                )

                create_inventory_transaction(
                    inventory=inventory,
                    source=receipt_item,
                    transaction_type=InventoryTransaction.TransactionType.RECEIPT,
                    quantity_change=qty,
                    cost_impact=qty * cost,
                )

                po_item.update_po_item_status()

            po.update_po_delivery_status()
            po.update_po_payment_status()
            po.update_po_status()
        self.stdout.write(f"      Received all items → delivery: {po.delivery_status}")

    # ------------------------------------------------------------------
    # Phase 6 — Transformations (boxed → coupled)
    # ------------------------------------------------------------------
    def _seed_transformations(self, user, products):
        self.stdout.write("\n  --- Transformations (Boxed → Coupled) ---")

        bajaj_boxer = products[1]   # Bajaj Boxer 100
        honda_cg = products[0]      # Honda CG 125
        yamaha_fz = products[8]     # Yamaha FZ 150

        bajaj_coupled = Product.objects.get(
            brand=bajaj_boxer.brand,
            modelname=bajaj_boxer.modelname,
            type_variant=Product.TypeVariant.COUPLED,
        )
        honda_coupled = Product.objects.get(
            brand=honda_cg.brand,
            modelname=honda_cg.modelname,
            type_variant=Product.TypeVariant.COUPLED,
        )
        yamaha_coupled = Product.objects.get(
            brand=yamaha_fz.brand,
            modelname=yamaha_fz.modelname,
            type_variant=Product.TypeVariant.COUPLED,
        )

        self._transform_batch(user, "TRF-1 (Bajaj Boxer 100 x5)", bajaj_boxer, bajaj_coupled, 5, Decimal("15000"))
        self._transform_batch(user, "TRF-2 (Honda CG 125 x3)", honda_cg, honda_coupled, 3, Decimal("12000"))
        self._transform_batch(user, "TRF-3 (Yamaha FZ 150 x2)", yamaha_fz, yamaha_coupled, 2, Decimal("10000"))

    def _transform_batch(self, user, label, source_product, target_product, count, service_fee):
        with db_transaction.atomic():
            transformation = Transformation.objects.create(
                service_fee=service_fee,
                transformation_date=_days_ago(20),
                created_by=user,
                updated_by=user,
            )

            raw_fee = service_fee / count
            service_fee_per = raw_fee.quantize(Decimal("0.01"))

            inventory = Inventory.objects.select_for_update().get(product=source_product)

            for _i in range(count):
                if inventory.quantity < 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Skipped {label}: insufficient stock for {source_product.modelname}"
                        )
                    )
                    continue

                inventory.quantity -= 1
                inventory.save(update_fields=["quantity", "updated_at"])

                fifo_cost, consumptions = _deplete_fifo_layers(source_product, 1)
                unit_cost = fifo_cost + service_fee_per

                consumed_layer = consumptions[0]["layer"] if consumptions else None

                item = TransformationItem(
                    transformation=transformation,
                    source_product=source_product,
                    target_product=target_product,
                    engine_number=_random_eng(),
                    chassis_number=_random_chs(),
                    allocated_service_fee=service_fee_per,
                    unit_cost_at_transformation=unit_cost,
                    consumed_layer=consumed_layer,
                    created_by=user,
                    updated_by=user,
                )
                item.save()

                create_inventory_transaction(
                    inventory=inventory,
                    source=item,
                    transaction_type=InventoryTransaction.TransactionType.TRANSFORMATION,
                    quantity_change=-1,
                    cost_impact=fifo_cost,
                )

            _recalculate_assembly_cost(target_product)

        self.stdout.write(f"    {label}: {count} units, service fee ₦{service_fee:,.2f}")

    # ------------------------------------------------------------------
    # Phase 7 — Customer Deposits
    # ------------------------------------------------------------------
    def _seed_deposits(self, user, customers):
        self.stdout.write("\n  --- Customer Deposits ---")

        deposit_schedule = [
            (customers[0], Decimal("450000"), _days_ago(35)),   # Ahmed Ibrahim
            (customers[1], Decimal("800000"), _days_ago(33)),   # Chidi Okafor
            (customers[2], Decimal("1000000"), _days_ago(30)),  # Musa Bello (part 1)
            (customers[2], Decimal("1000000"), _days_ago(25)),  # Musa Bello (part 2)
            (customers[3], Decimal("800000"), _days_ago(33)),   # Fatima Usman
            (customers[4], Decimal("1500000"), _days_ago(30)),  # Oluwaseun Adeyemi
            (customers[5], Decimal("500000"), _days_ago(28)),   # Ibe Okonkwo
            (customers[8], Decimal("350000"), _days_ago(20)),   # Zainab Abdullahi
            (customers[10], Decimal("420000"), _days_ago(18)),  # Grace Okonkwo
            (customers[11], Decimal("350000"), _days_ago(15)),  # Ibrahim Tanko
        ]

        for customer, amount, created_at in deposit_schedule:
            account = customer.deposit_account
            existing = Transaction.objects.filter(
                account=account,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                status=Transaction.Status.ACTIVE,
            ).exists()

            if existing:
                continue

            txn = record_deposit(
                account=account,
                amount=amount,
                note="Deposit payment — seed data",
                user=user,
                created_at=created_at,
            )
            self.stdout.write(
                f"    ₦{amount:,.2f} → {customer.full_name} ({txn.reference_number})"
            )

    # ------------------------------------------------------------------
    # Phase 8 — Purchase Agreements
    # ------------------------------------------------------------------
    def _seed_purchase_agreements(self, user, customers, products):
        self.stdout.write("\n  --- Purchase Agreements ---")

        if PurchaseAgreement.objects.exists():
            self.stdout.write("    Agreements already exist — skipping.")
            return

        honda_cg = products[0]
        bajaj_boxer = products[1]
        tvs_star = products[2]
        yamaha_ybr = products[3]
        suzuki_gd = products[4]
        bajaj_ct = products[6]
        bajaj_pulsar = products[10]

        yamaha_fz_coupled = Product.objects.get(
            brand__name="Yamaha", modelname="FZ 150",
            type_variant=Product.TypeVariant.COUPLED,
        )
        bajaj_boxer_coupled = Product.objects.get(
            brand__name="Bajaj", modelname="Boxer 100",
            type_variant=Product.TypeVariant.COUPLED,
        )

        # Agreement 1: Ahmed Ibrahim — 1x Honda CG 125
        ag1 = create_purchase_agreement(
            account=customers[0].deposit_account,
            line_items_data=[
                {"product": honda_cg, "quantity_ordered": 1, "price_per_unit": Decimal("450000")},
            ],
            user=user,
        )
        self.stdout.write(f"    {ag1.purchase_agreement_number}: Ahmed Ibrahim → {honda_cg.modelname} x1 @ ₦450,000")

        # Agreement 2: Chidi Okafor — 2x Bajaj Boxer 100 (boxed) + 1x coupled
        ag2 = create_purchase_agreement(
            account=customers[1].deposit_account,
            line_items_data=[
                {"product": bajaj_boxer, "quantity_ordered": 2, "price_per_unit": Decimal("360000")},
                {"product": bajaj_boxer_coupled, "quantity_ordered": 1, "price_per_unit": Decimal("380000")},
            ],
            user=user,
        )
        self.stdout.write(
            f"    {ag2.purchase_agreement_number}: Chidi Okafor → "
            f"{bajaj_boxer.modelname} x2 (boxed) + x1 (coupled), ₦1,100,000 total"
        )

        # Agreement 3: Fatima Usman — 1x TVS Star 110 + 1x Suzuki GD 110
        ag3 = create_purchase_agreement(
            account=customers[3].deposit_account,
            line_items_data=[
                {"product": tvs_star, "quantity_ordered": 1, "price_per_unit": Decimal("340000")},
                {"product": suzuki_gd, "quantity_ordered": 1, "price_per_unit": Decimal("350000")},
            ],
            user=user,
        )
        self.stdout.write(f"    {ag3.purchase_agreement_number}: Fatima Usman → {tvs_star.modelname} + {suzuki_gd.modelname}, ₦690,000")

        # Agreement 4: Oluwaseun Adeyemi — 2x Bajaj Pulsar + 1x Yamaha FZ (coupled)
        ag4 = create_purchase_agreement(
            account=customers[4].deposit_account,
            line_items_data=[
                {"product": bajaj_pulsar, "quantity_ordered": 2, "price_per_unit": Decimal("500000")},
                {"product": yamaha_fz_coupled, "quantity_ordered": 1, "price_per_unit": Decimal("490000")},
            ],
            user=user,
        )
        self.stdout.write(
            f"    {ag4.purchase_agreement_number}: Oluwaseun Adeyemi → "
            f"{bajaj_pulsar.modelname} x2 + {yamaha_fz_coupled.modelname} (coupled) x1, ₦1,490,000"
        )

        # Agreement 5: Ibe Okonkwo — 1x Bajaj Pulsar
        ag5 = create_purchase_agreement(
            account=customers[5].deposit_account,
            line_items_data=[
                {"product": bajaj_pulsar, "quantity_ordered": 1, "price_per_unit": Decimal("500000")},
            ],
            user=user,
        )
        self.stdout.write(f"    {ag5.purchase_agreement_number}: Ibe Okonkwo → {bajaj_pulsar.modelname} x1 @ ₦500,000")

        # Agreement 6: Zainab Abdullahi — 1x Bajaj CT 100
        ag6 = create_purchase_agreement(
            account=customers[8].deposit_account,
            line_items_data=[
                {"product": bajaj_ct, "quantity_ordered": 1, "price_per_unit": Decimal("330000")},
            ],
            user=user,
        )
        self.stdout.write(f"    {ag6.purchase_agreement_number}: Zainab Abdullahi → {bajaj_ct.modelname} x1 @ ₦330,000")

        # Agreement 7: Grace Okonkwo — 1x Yamaha YBR 125
        ag7 = create_purchase_agreement(
            account=customers[10].deposit_account,
            line_items_data=[
                {"product": yamaha_ybr, "quantity_ordered": 1, "price_per_unit": Decimal("420000")},
            ],
            user=user,
        )
        self.stdout.write(f"    {ag7.purchase_agreement_number}: Grace Okonkwo → {yamaha_ybr.modelname} x1 @ ₦420,000")

    # ------------------------------------------------------------------
    # Phase 9 — CFA Agreements
    # ------------------------------------------------------------------
    def _seed_cfa_agreements(self, user, customers):
        self.stdout.write("\n  --- CFA Agreements ---")

        if CfaAgreement.objects.exists():
            self.stdout.write("    CFA agreements already exist — skipping.")
            return

        # CFA 1: Musa Bello — large allocation, partially fulfilled
        cfa1 = create_cfa_agreement(
            account=customers[2].deposit_account,   # Musa Bello
            amount_naira=Decimal("1500000"),
            exchange_rate=Decimal("1800"),
            user=user,
        )
        self.stdout.write(
            f"    {cfa1.cfa_agreement_number}: Musa Bello — "
            f"₦1,500,000 @ ₦1,800/1,000 XOF → expects ~{cfa1.expected_cfa_amount:,} XOF"
        )

        # Fulfill CFA 1 partially
        f1 = record_cfa_fulfillment(
            agreement_id=cfa1.pk,
            cfa_amount=Decimal("450000"),
            notes="First disbursement to Banque Atlantique, Cotonou — seed data",
            user=user,
            created_at=_days_ago(10),
        )
        self.stdout.write(f"      → Fulfilled 450,000 XOF (₦{f1.cfa_amount_disbursed_to_naira:,.2f}) — PARTIALLY_FULFILLED")

        # CFA 2: Oluwaseun Adeyemi — small allocation, fully fulfilled
        cfa2 = create_cfa_agreement(
            account=customers[4].deposit_account,   # Oluwaseun Adeyemi
            amount_naira=Decimal("50000"),
            exchange_rate=Decimal("1850"),
            user=user,
        )
        self.stdout.write(
            f"    {cfa2.cfa_agreement_number}: Oluwaseun Adeyemi — "
            f"₦50,000 @ ₦1,850/1,000 XOF → ~{cfa2.expected_cfa_amount:,} XOF"
        )

        f2 = record_cfa_fulfillment(
            agreement_id=cfa2.pk,
            cfa_amount=Decimal("27000"),
            notes="Fulfilled in full — seed data",
            user=user,
            created_at=_days_ago(8),
        )
        self.stdout.write(f"      → Fulfilled 27,000 XOF (₦{f2.cfa_amount_disbursed_to_naira:,.2f}) — FULFILLED")

    # ------------------------------------------------------------------
    # Phase 10 — Sales
    # ------------------------------------------------------------------
    def _seed_sales(self, user, customers, products):
        self.stdout.write("\n  --- Sales ---")

        if Sale.objects.exists():
            self.stdout.write("    Sales already exist — skipping.")
            return

        # Re-fetch ALL products from DB to avoid stale cached inventory
        product_pks = [p.pk for p in products]
        fresh = {p.pk: p for p in Product.objects.filter(pk__in=product_pks)}

        def _get_boxed(index):
            return fresh[products[index].pk]

        honda_cg = _get_boxed(0)
        bajaj_boxer = _get_boxed(1)
        tvs_star = _get_boxed(2)
        yamaha_ybr = _get_boxed(3)
        suzuki_hayate = _get_boxed(9)
        bajaj_ct = _get_boxed(6)
        bajaj_pulsar = _get_boxed(10)
        honda_ace = _get_boxed(5)

        yamaha_fz_coupled = Product.objects.get(
            brand__name="Yamaha", modelname="FZ 150",
            type_variant=Product.TypeVariant.COUPLED,
        )
        bajaj_boxer_coupled = Product.objects.get(
            brand__name="Bajaj", modelname="Boxer 100",
            type_variant=Product.TypeVariant.COUPLED,
        )

        # --- Cash/Bank Transfer Sales (walk-in customers) ---

        # Sale 1: Aisha Suleiman — Bajaj CT 100 (cash)
        self._make_cash_sale(user, customers[6], bajaj_ct, 1, Decimal("390000"))

        # Sale 2: Emeka Nwankwo — Suzuki Hayate 110 (cash)
        self._make_cash_sale(user, customers[7], suzuki_hayate, 1, Decimal("400000"))

        # Sale 3: Yusuf Adamu — Honda Ace 110 (bank transfer)
        self._make_cash_sale(user, customers[9], honda_ace, 1, Decimal("460000"))

        # --- Deposit Sales (fulfilling agreements) ---

        # Sale 4: Ahmed Ibrahim — Honda CG 125 (fulfills agreement #1)
        ag1 = PurchaseAgreement.objects.get(account=customers[0].deposit_account)
        ag1_l1 = ag1.agreement_line_items.filter(is_current_version=True).first()
        self._make_deposit_sale(user, customers[0], ag1, honda_cg, ag1_l1, 1)

        # Sale 5: Chidi Okafor — Bajaj Boxer 100 boxed (partial fulfillment, agreement #2)
        ag2 = PurchaseAgreement.objects.get(account=customers[1].deposit_account)
        ag2_l1_boxed = ag2.agreement_line_items.filter(
            product=bajaj_boxer, is_current_version=True
        ).first()
        self._make_deposit_sale(user, customers[1], ag2, bajaj_boxer, ag2_l1_boxed, 1)

        # Sale 6: Chidi Okafor — Bajaj Boxer 100 coupled (further partial, agreement #2)
        ag2_l1_coupled = ag2.agreement_line_items.filter(
            product=bajaj_boxer_coupled, is_current_version=True
        ).first()
        coupled_item = TransformationItem.objects.filter(
            target_product=bajaj_boxer_coupled,
            status=TransformationItem.Status.AVAILABLE,
        ).first()
        if coupled_item and ag2_l1_coupled:
            self._make_deposit_coupled_sale(
                user, customers[1], ag2, coupled_item, ag2_l1_coupled, Decimal("380000")
            )

        # Sale 7: Fatima Usman — TVS Star 110 (partial fulfillment, agreement #3)
        ag3 = PurchaseAgreement.objects.get(account=customers[3].deposit_account)
        ag3_l1 = ag3.agreement_line_items.filter(
            product=tvs_star, is_current_version=True
        ).first()
        self._make_deposit_sale(user, customers[3], ag3, tvs_star, ag3_l1, 1)

        # Sale 8: Oluwaseun Adeyemi — Yamaha FZ 150 coupled (partial, agreement #4)
        ag4 = PurchaseAgreement.objects.get(account=customers[4].deposit_account)
        ag4_l1_coupled = ag4.agreement_line_items.filter(
            product=yamaha_fz_coupled, is_current_version=True
        ).first()
        coupled_fz = TransformationItem.objects.filter(
            target_product=yamaha_fz_coupled,
            status=TransformationItem.Status.AVAILABLE,
        ).first()
        if coupled_fz and ag4_l1_coupled:
            self._make_deposit_coupled_sale(
                user, customers[4], ag4, coupled_fz, ag4_l1_coupled, Decimal("490000")
            )

        # Sale 9: Ibe Okonkwo — Bajaj Pulsar (fulfills agreement #5)
        ag5 = PurchaseAgreement.objects.get(account=customers[5].deposit_account)
        ag5_l1 = ag5.agreement_line_items.filter(is_current_version=True).first()
        self._make_deposit_sale(user, customers[5], ag5, bajaj_pulsar, ag5_l1, 1)

        # Sale 10: Zainab Abdullahi — Bajaj CT 100 (fulfills agreement #6)
        ag6 = PurchaseAgreement.objects.get(account=customers[8].deposit_account)
        ag6_l1 = ag6.agreement_line_items.filter(is_current_version=True).first()
        self._make_deposit_sale(user, customers[8], ag6, bajaj_ct, ag6_l1, 1)

        # Sale 11: Grace Okonkwo — Yamaha YBR 125 (fulfills agreement #7)
        ag7 = PurchaseAgreement.objects.get(account=customers[10].deposit_account)
        ag7_l1 = ag7.agreement_line_items.filter(is_current_version=True).first()
        self._make_deposit_sale(user, customers[10], ag7, yamaha_ybr, ag7_l1, 1)

    def _make_cash_sale(self, user, customer, product, qty, price):
        sale = Sale(
            customer=customer,
            payment_method=Sale.PaymentMethod.CASH,
            created_by=user,
            updated_by=user,
        )
        boxed_item = BoxedSale(
            sale=sale, product=product, quantity=qty, price=price,
            created_by=user, updated_by=user,
        )
        try:
            create_sale(sale=sale, boxed_items=[boxed_item], coupled_items=[], user=user)
            self.stdout.write(
                f"    {sale.sale_number}: {qty}x {product.modelname} "
                f"→ {customer.full_name} (CASH) @ ₦{price:,.2f}"
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Skipped cash sale for {customer.full_name}: {e}"))

    def _make_deposit_sale(self, user, customer, agreement, product, agreement_line_item, qty):
        sale = Sale(
            customer=customer,
            payment_method=Sale.PaymentMethod.FROM_DEPOSIT,
            agreement=agreement,
            created_by=user,
            updated_by=user,
        )
        boxed_item = BoxedSale(
            sale=sale, product=product, quantity=qty,
            agreement_line_item=agreement_line_item,
            created_by=user, updated_by=user,
        )
        try:
            create_sale(sale=sale, boxed_items=[boxed_item], coupled_items=[], user=user)
            self.stdout.write(
                f"    {sale.sale_number}: {qty}x {product.modelname} "
                f"→ {customer.full_name} (DEPOSIT) @ ₦{agreement_line_item.price_per_unit:,.2f}"
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Skipped deposit sale for {customer.full_name}: {e}"))

    def _make_deposit_coupled_sale(self, user, customer, agreement, transformation_item, agreement_line_item, price):
        sale = Sale(
            customer=customer,
            payment_method=Sale.PaymentMethod.FROM_DEPOSIT,
            agreement=agreement,
            created_by=user,
            updated_by=user,
        )
        coupled_item = CoupledSale(
            sale=sale, transformation_item=transformation_item,
            agreement_line_item=agreement_line_item, price=price,
            created_by=user, updated_by=user,
        )
        try:
            create_sale(sale=sale, boxed_items=[], coupled_items=[coupled_item], user=user)
            target_name = transformation_item.target_product.modelname if transformation_item.target_product else "unknown"
            self.stdout.write(
                f"    {sale.sale_number}: 1x {target_name} (coupled, ENG: ...{transformation_item.engine_number[-5:]}) "
                f"→ {customer.full_name} (DEPOSIT) @ ₦{price:,.2f}"
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"    Skipped coupled sale for {customer.full_name}: {e}"))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    def _print_summary(self, customers, products, suppliers):
        self.stdout.write("\n")
        self.stdout.write("=" * 60)
        self.stdout.write("  DEMO DATA SUMMARY")
        self.stdout.write("=" * 60)

        user_count = CustomUser.objects.count()
        customer_count = Customer.objects.count()
        product_count = Product.objects.count()
        supplier_count = Supplier.objects.count()
        po_count = PurchaseOrder.objects.count()
        receipt_count = GoodsReceipt.objects.count()
        deposit_count = Transaction.objects.filter(
            transaction_type=Transaction.TransactionType.DEPOSIT,
            status=Transaction.Status.ACTIVE,
        ).count()
        total_deposits = Transaction.objects.filter(
            transaction_type=Transaction.TransactionType.DEPOSIT,
            status=Transaction.Status.ACTIVE,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        sale_count = Sale.objects.filter(status=Sale.Status.ACTIVE).count()
        total_sales = Decimal("0.00")
        for sale in Sale.objects.filter(status=Sale.Status.ACTIVE):
            total_sales += sale.sales_total

        ag_count = PurchaseAgreement.objects.count()
        cfa_count = CfaAgreement.objects.count()
        cfa_ful_count = CfaFulfillment.objects.filter(status=CfaFulfillment.Status.ACTIVE).count()
        trans_count = Transformation.objects.filter(status=Transformation.Status.ACTIVE).count()
        trans_item_count = TransformationItem.objects.filter(
            status=TransformationItem.Status.AVAILABLE
        ).count()
        trans_sold_count = TransformationItem.objects.filter(
            status=TransformationItem.Status.SOLD
        ).count()
        boxed_stock = Inventory.objects.aggregate(total=Sum("quantity"))["total"] or 0

        total_po_value = Decimal("0.00")
        for po in PurchaseOrder.objects.all():
            for poi in po.po_items.all():
                total_po_value += poi.unit_price_at_order * poi.ordered_quantity

        self.stdout.write(f"  Users:             {user_count} (admin/staff)")
        self.stdout.write(f"  Customers:         {customer_count}")
        self.stdout.write(f"  Products:          {product_count} (boxed + coupled)")
        self.stdout.write(f"  Suppliers:         {supplier_count}")
        self.stdout.write(f"  Purchase Orders:   {po_count} (total value: ₦{total_po_value:,.2f})")
        self.stdout.write(f"  Goods Receipts:    {receipt_count}")
        self.stdout.write(f"  Stock on Hand:     {boxed_stock} units (boxed)")
        self.stdout.write(f"  Transformations:   {trans_count} ({trans_item_count} available coupled, {trans_sold_count} sold)")
        self.stdout.write(f"  Deposits:          {deposit_count} transactions (total: ₦{total_deposits:,.2f})")
        self.stdout.write(f"  Agreements:        {ag_count}")
        self.stdout.write(f"  CFA Agreements:    {cfa_count} ({cfa_ful_count} active fulfillments)")
        self.stdout.write(f"  Sales:             {sale_count} (total value: ₦{total_sales:,.2f})")
        self.stdout.write("=" * 60)
        self.stdout.write("  Login: admin / demo1234  |  staff / demo1234")
        self.stdout.write("=" * 60)
