from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone

from account.models import CustomUser
from customer.models import Customer, DepositAccount, Transaction, Sale, BoxedSale
from customer.services import record_deposit, create_sale
from inventory.models import Brand, Product, Inventory, InventoryCostLayer, InventoryTransaction
from inventory.utils import create_inventory_transaction
from supply_chain.models import (
    Supplier, PurchaseOrder, PurchaseOrderItem, Payment,
    GoodsReceipt, GoodsReceiptItem,
)
from supply_chain.services import record_supplier_payment


class Command(BaseCommand):
    help = "Seeds demo data for a Nigerian motorcycle dealership showcase."

    def handle(self, *args, **options):
        admin_user = self._seed_users()
        self._seed_brands(admin_user)
        products = self._seed_products(admin_user)
        suppliers = self._seed_suppliers(admin_user)
        customers = self._seed_customers(admin_user)

        any_pos = PurchaseOrder.objects.exists()
        if not any_pos:
            self._seed_supply_chain(admin_user, products, suppliers)
            self._seed_deposits(admin_user, customers)
            self._seed_sales(admin_user, customers, products)
        else:
            self.stdout.write("  Purchase orders already exist — skipping financial activity seed.")

        self.stdout.write(self.style.SUCCESS("\nDemo data seeding complete!"))

    def _seed_users(self):
        admin, created = CustomUser.objects.get_or_create(
            username="admin",
            defaults={
                "is_superuser": True,
                "is_staff": True,
                "email": "admin@demo.com",
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
                "email": "staff@demo.com",
            },
        )
        if created:
            staff.set_password("demo1234")
            staff.save()
            self.stdout.write(self.style.SUCCESS("  Created staff user: staff / demo1234"))
        else:
            self.stdout.write("  Staff user 'staff' already exists.")

        return admin

    def _seed_brands(self, user):
        brand_names = ["Honda", "Bajaj", "TVS", "Yamaha", "Suzuki"]
        for name in brand_names:
            _, created = Brand.objects.get_or_create(
                name=name,
                defaults={"created_by": user, "updated_by": user},
            )
            if created:
                self.stdout.write(f"  Created brand: {name}")
            else:
                self.stdout.write(f"  Brand '{name}' already exists.")

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
            ("Bajaj", "Discover 125", "125cc commuter", Decimal("390000")),
            ("Honda", "Wave 110", "110cc step-through", Decimal("370000")),
            ("TVS", "Max 125", "125cc cargo motorcycle", Decimal("380000")),
            ("Yamaha", "Crux 100", "100cc economy", Decimal("320000")),
            ("Suzuki", "DR 200", "200cc enduro motorcycle", Decimal("580000")),
        ]

        created_products = []
        for brand_name, modelname, description, unit_price in products_info:
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
                created_products.append((product, unit_price))
                self.stdout.write(f"    Created: {brand_name} {modelname} (boxed)")
                coupled = Product.objects.filter(
                    brand=brand,
                    modelname=modelname,
                    type_variant=Product.TypeVariant.COUPLED,
                ).first()
                if coupled:
                    self.stdout.write(f"      → auto-created coupled variant: {coupled.sku}")
            else:
                created_products.append((product, unit_price))
                self.stdout.write(f"    Exists: {brand_name} {modelname}")

        return created_products

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
            supplier, created = Supplier.objects.get_or_create(
                company_name=info["company_name"],
                defaults={
                    "full_name": info["full_name"],
                    "phone": info["phone"],
                    "address": info["address"],
                    "created_by": user,
                    "updated_by": user,
                },
            )
            if created:
                self.stdout.write(f"  Created supplier: {supplier.company_name}")
            else:
                self.stdout.write(f"  Supplier '{supplier.company_name}' already exists.")
            suppliers.append(supplier)

        return suppliers

    def _seed_customers(self, user):
        customers_info = [
            ("Ahmed Ibrahim", "08031112233"),
            ("Chidi Okafor", "08052223344"),
            ("Musa Bello", "08063334455"),
            ("Fatima Usman", "08074445566"),
            ("Oluwaseun Adeyemi", "08085556677"),
            ("Ibe Okonkwo", "08096667788"),
            ("Aisha Suleiman", "08107778899"),
            ("Emeka Nwankwo", "08118889900"),
            ("Zainab Abdullahi", "08129990011"),
            ("Yusuf Adamu", "08130001122"),
        ]

        customers = []
        for full_name, phone in customers_info:
            customer, created = Customer.objects.get_or_create(
                full_name=full_name,
                defaults={
                    "phone": phone,
                    "created_by": user,
                    "updated_by": user,
                },
            )
            if created:
                account = customer.deposit_account
                self.stdout.write(f"  Created customer: {full_name} (acct: {account.account_number})")
            else:
                self.stdout.write(f"  Customer '{full_name}' already exists.")
            customers.append(customer)

        return customers

    def _seed_supply_chain(self, user, products, suppliers):
        self.stdout.write("\n  --- Seeding supply chain (POs + Payments + Receipts) ---")

        po1 = self._create_po(
            user, suppliers[0],
            [
                (products[0][0], 10, products[0][1]),   # Honda CG 125 x10
                (products[1][0], 15, products[1][1]),   # Bajaj Boxer 100 x15
                (products[3][0], 8, products[3][1]),    # Yamaha YBR 125 x8
                (products[2][0], 12, products[2][1]),   # TVS Star 110 x12
            ],
            delivery_cost=Decimal("50000"),
            title="PO-1 (Automatic Parts Nigeria Ltd)",
        )

        po2 = self._create_po(
            user, suppliers[1],
            [
                (products[4][0], 10, products[4][1]),   # Suzuki GD 110 x10
                (products[5][0], 8, products[5][1]),    # Honda Ace 110 x8
                (products[10][0], 6, products[10][1]),  # Bajaj Pulsar 150 x6
                (products[8][0], 5, products[8][1]),    # Yamaha FZ 150 x5
            ],
            delivery_cost=Decimal("35000"),
            title="PO-2 (Lagos Motorcycle Supplies)",
        )

        po3 = self._create_po(
            user, suppliers[2],
            [
                (products[7][0], 8, products[7][1]),    # TVS Apache 160 x8
                (products[14][0], 6, products[14][1]),  # Suzuki Gixxer 150 x6
                (products[11][0], 7, products[11][1]),  # Honda CBF 150 x7
                (products[13][0], 5, products[13][1]),  # Yamaha XTZ 125 x5
            ],
            delivery_cost=Decimal("40000"),
            title="PO-3 (Kano Wholesale Ventures)",
        )

        all_pos = [po1, po2, po3]
        for po in all_pos:
            self._pay_and_receive(po, user)

    def _create_po(self, user, supplier, items_data, delivery_cost, title):
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

        self.stdout.write(f"    {title}: ₦{total_amount:,.2f} total across {len(items_data)} products")
        return po

    def _pay_and_receive(self, po, user):
        total = sum(
            item.ordered_quantity * item.unit_price_at_order
            for item in po.po_items.all()
        )

        record_supplier_payment(
            po=po,
            amount=total,
            method=Payment.PaymentMethod.TRANSFER,
            user=user,
            remark="Full payment — seed data",
        )
        self.stdout.write(f"      Paid ₦{total:,.2f} → delivery_status: {po.delivery_status}")

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
                inventory.save(update_fields=["quantity", "weighted_average_cost", "updated_at"])

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

        self.stdout.write(f"      Received all goods → delivery_status: {po.delivery_status}, total status: {po.status}")

    def _seed_deposits(self, user, customers):
        self.stdout.write("\n  --- Seeding customer deposits ---")

        deposit_amounts = [
            (customers[0], Decimal("500000")),   # Ahmed Ibrahim
            (customers[1], Decimal("350000")),   # Chidi Okafor
            (customers[2], Decimal("600000")),   # Musa Bello
            (customers[3], Decimal("200000")),   # Fatima Usman
            (customers[4], Decimal("800000")),   # Oluwaseun Adeyemi
            (customers[5], Decimal("450000")),   # Ibe Okonkwo
        ]

        past_date = timezone.now() - timezone.timedelta(days=30)
        for customer, amount in deposit_amounts:
            account = customer.deposit_account
            existing = Transaction.objects.filter(
                account=account,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                status=Transaction.Status.ACTIVE,
            ).exists()

            if existing:
                self.stdout.write(f"    Deposits exist for {customer.full_name} — skipping.")
                continue

            record_deposit(
                account=account,
                amount=amount,
                note="Demo seed deposit",
                user=user,
                created_at=past_date,
            )
            self.stdout.write(f"    ₦{amount:,.2f} deposited → {customer.full_name}")

    def _seed_sales(self, user, customers, products):
        self.stdout.write("\n  --- Seeding cash sales ---")

        if Sale.objects.exists():
            self.stdout.write("    Sales already exist — skipping.")
            return

        product_pks = [p[0].pk for p in products]
        fresh_products = {
            p.pk: p
            for p in Product.objects.filter(pk__in=product_pks)
        }

        sales_data = [
            (customers[6], fresh_products[products[0][0].pk], 1, Decimal("550000")),   # Aisha → Honda CG 125
            (customers[7], fresh_products[products[1][0].pk], 1, Decimal("440000")),   # Emeka → Bajaj Boxer 100
            (customers[8], fresh_products[products[2][0].pk], 1, Decimal("420000")),   # Zainab → TVS Star 110
            (customers[9], fresh_products[products[3][0].pk], 1, Decimal("510000")),   # Yusuf → Yamaha YBR 125
        ]

        for customer, product, qty, price in sales_data:
            sale = Sale(
                customer=customer,
                payment_method=Sale.PaymentMethod.CASH,
                created_by=user,
                updated_by=user,
            )

            boxed_item = BoxedSale(
                sale=sale,
                product=product,
                quantity=qty,
                price=price,
                created_by=user,
                updated_by=user,
            )

            try:
                create_sale(
                    sale=sale,
                    boxed_items=[boxed_item],
                    coupled_items=[],
                    user=user,
                )
                self.stdout.write(
                    f"    Sale {sale.sale_number}: {qty}x {product.modelname} "
                    f"→ {customer.full_name} @ ₦{price:,.2f}"
                )
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"    Skipped sale for {customer.full_name}: {e}"
                    )
                )
