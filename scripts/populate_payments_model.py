import random
from faker import Faker
from supply_chain.models import PurchaseOrder, Payment
from account.models import CustomUser


def run():
    # --- Configuration ---
    NUMBER_OF_PAYMENTS = 50
    # ---------------------

    fake = Faker()

    purchase_orders = list(PurchaseOrder.objects.all())
    user = CustomUser.objects.first()

    if not purchase_orders:
        print("Cannot create payments. No purchase orders found in the database.")
        return

    if not user:
        print("Warning: No user found. 'created_by' and 'updated_by' will be None.")
        user = None

    created_count = 0
    for _ in range(NUMBER_OF_PAYMENTS):
        po = random.choice(purchase_orders)

        # Determine a realistic payment amount (e.g., between 10% and 100% of PO total)
        po_total = po.total_amount or 1000  # Use a fallback value if total is 0 or None
        if po_total > 0:
            amount = round(random.uniform(float(po_total) * 0.1, float(po_total)), 2)
        else:
            amount = round(random.uniform(100.00, 5000.00), 2)

        # Randomly choose from model choices
        payment_method = random.choice(
            [choice[0] for choice in Payment.PaymentMethod.choices]
        )
        status = random.choice([choice[0] for choice in Payment.Status.choices])

        try:
            Payment.objects.create(
                purchase_order=po,
                amount_paid=amount,
                payment_method=payment_method,
                status=status,
                remark=fake.sentence(nb_words=10),
                created_by=user,
                updated_by=user,
            )
            created_count += 1
        except Exception as e:
            print(f"Could not create payment for PO {po.po_number}. Error: {e}")

    print(f"Successfully created {created_count} supplier payments.")
