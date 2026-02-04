import panda as pd
import os
from decimal import Decimal
from django.db import transaction
from django.db.models import ObjectDoesNotExist
from django.utils import timezone
from datetime import datetime
from inventory.models import TransformationItem
from customer.models import Customer, Sale, CoupledSale, TransformationItem, Customer
from mrms import settings


BASE_DIR = settings.BASE_DIR
CSV_DATA_DIR = os.path.join(BASE_DIR, "csv_data")
CSV_PATH = os.path.join(CSV_DATA_DIR, "sale.csv")


# Payment method mapping from CSV data to model choices
PAYMENT_METHOD_MAP = {
    "TRANSFER": Sale.PaymentMethod.BANK_TRANSFER,
    "CASH": Sale.PaymentMethod.CASH,
}


def run():
    """
    Imports sale data from the CSV file into the Django Sale and CoupledSale models.
    """
    if not os.path.exists(CSV_PATH):
        print(f"Error: CSV file not found at '{CSV_PATH}'")
        return

    try:
        df = pd.read_csv(CSV_PATH)
        # Convert 'sale_date' to a datetime object immediately
        df["sale_date"] = pd.to_datetime(df["sale_date"])
    except Exception as e:
        print(f"Error loading CSV data: {e}")
        return

    print(f"Starting sale import for {len(df)} rows...")
    success_count = 0
    skip_count = 0

    # Wrap the entire process in a transaction for atomicity
    with transaction.atomic():
        for index, row in df.iterrows():
            engine_no = row["engine_no"].strip()
            chassis_no = row["chassis_no"].strip()
            customer_id = str(row["customer_id"])
            sale_date = row["sale_date"]
            payment_type_csv = row["payment_type"].upper().strip()
            final_price = Decimal(str(row["final_price"]))
            # status_csv = row["status"].lower().strip()

            # 1. Look up TransformationItem and Check Status (Skip Logic)
            try:
                transformation_item = TransformationItem.objects.get(
                    engine_number__iexact=engine_no,
                    chassis_number__iexact=chassis_no,
                )

                if transformation_item.status == TransformationItem.Status.SOLD:
                    print(
                        f"SKIP: Row {index + 1}: TransformationItem (Chassis: {chassis_no}) already SOLD. Ignoring record."
                    )
                    skip_count += 1
                    continue

            except ObjectDoesNotExist:
                print(
                    f"ERROR: Row {index + 1}: TransformationItem not found for Engine: {engine_no}, Chassis: {chassis_no}. Skipping."
                )
                skip_count += 1
                continue
            except Exception as e:
                print(
                    f"ERROR: Row {index + 1}: TransformationItem lookup failed for {chassis_no}. Skipping. Error: {e}"
                )
                skip_count += 1
                continue

            # 2. Look up Customer
            try:
                # Use 'idd' field for lookup as specified by the user
                customer = Customer.objects.get(idd=customer_id)
            except ObjectDoesNotExist:
                print(
                    f"ERROR: Row {index + 1}: Customer with idd '{customer_id}' not found. Skipping."
                )
                skip_count += 1
                continue

            # 3. Create Sale Record
            try:
                payment_method = PAYMENT_METHOD_MAP.get(payment_type_csv)
                if not payment_method:
                    print(
                        f"ERROR: Row {index + 1}: Unknown payment type '{payment_type_csv}'. Skipping."
                    )
                    skip_count += 1
                    continue

                # Use current time zone for sale_date to prevent a warning/error if it is naive
                sale_date = timezone.make_aware(sale_date)

                sale = Sale.objects.create(
                    customer=customer,
                    payment_method=payment_method,
                    sale_date=sale_date,
                    # status=status_csv,
                    # agreement is left as None as per model/data constraints
                )
                # The .save() method on Sale calls .full_clean(), which validates the record.

            except Exception as e:
                print(
                    f"ERROR: Row {index + 1}: Failed to create Sale record for Customer {customer_id}. Skipping. Error: {e}"
                )
                skip_count += 1
                continue

            # 4. Create CoupledSale Record
            try:
                CoupledSale.objects.create(
                    sale=sale,
                    transformation_item=transformation_item,
                    price=final_price,
                    # agreement_line_item is left as None
                )

                # NOTE: The TransformationItem status update to 'SOLD' is handled
                # by an existing signal upon CoupledSale creation, as requested.

                success_count += 1
                print(
                    f"SUCCESS: Row {index + 1}: Created Sale '{sale.sale_number}' and CoupledSale for Chassis {chassis_no}"
                )

            except Exception as e:
                # If CoupledSale creation fails, the sale transaction should still roll back
                # because we are inside a larger transaction.atomic() block.
                print(
                    f"ERROR: Row {index + 1}: Failed to create CoupledSale for Sale {sale.sale_number}. Error: {e}"
                )
                # No need to explicitly skip/count here, as the outer transaction handles the error.
                raise e  # Re-raise to trigger rollback of the outer transaction (Sale creation included)

    print("\n--- Import Summary ---")
    print(f"Total Rows Processed: {len(df)}")
    print(f"Successful Sales Created: {success_count}")
    print(f"Rows Skipped (Item/Customer/Status Error): {skip_count}")
    print("----------------------")
