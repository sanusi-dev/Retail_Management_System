import csv
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from django.conf import settings
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from inventory.models import Transformation, TransformationItem, Product
from account.models import CustomUser

try:
    BASE_DIR = settings.BASE_DIR
    CSV_DATA_DIR = os.path.join(BASE_DIR, "csv_data")
except AttributeError:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CSV_DATA_DIR = os.path.join(BASE_DIR, "csv_data")

TRANSFORMATION_CSV_FILENAME = "serial.csv"
DATE_FORMATS = [
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
]


def get_csv_path(filename):
    return os.path.join(CSV_DATA_DIR, filename)


def parse_date(date_str):
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            naive_dt = datetime.strptime(date_str, fmt)
            return timezone.make_aware(naive_dt)
        except ValueError:
            continue
    return None


def run():
    try:
        system_user = CustomUser.objects.get(username="admin")
    except CustomUser.DoesNotExist:
        system_user = CustomUser.objects.first()
        if not system_user:
            print("FATAL ERROR: No users found. Cannot assign created_by fields.")
            return
        print(f"Warning: Using user {system_user.username} as fallback creator.")

    csv_path = get_csv_path(TRANSFORMATION_CSV_FILENAME)
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at '{csv_path}'.")
        return

    print(
        f"\n--- Starting Transformation Import from {TRANSFORMATION_CSV_FILENAME} ---"
    )

    grouped_data = defaultdict(list)

    total_rows_read = 0

    try:
        with open(csv_path, mode="r", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            for index, row in enumerate(reader):
                total_rows_read += 1
                raw_date = row.get("transformation_date", "")

                date_obj = parse_date(raw_date)
                if not date_obj:
                    print(f"SKIP ROW {index+1}: Invalid date format '{raw_date}'")
                    continue

                grouped_data[date_obj].append(row)

    except FileNotFoundError:
        print(f"ERROR: File not found at {csv_path}")
        return
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    print(
        f"Read {total_rows_read} rows. Found {len(grouped_data)} unique transformation dates."
    )

    transformations_created = 0
    items_created = 0
    items_skipped = 0

    sorted_dates = sorted(grouped_data.keys())

    with transaction.atomic():
        for t_date in sorted_dates:
            rows = grouped_data[t_date]

            batch_total_fee = Decimal("0.00")
            valid_rows_for_creation = []

            for row in rows:
                try:
                    fee_str = row.get("service_fee", "0").strip()
                    fee = Decimal(fee_str) if fee_str else Decimal("0")
                    batch_total_fee += fee
                    valid_rows_for_creation.append({"data": row, "fee": fee})
                except InvalidOperation:
                    print(f"Error parsing fee for row: {row}")
                    continue

            try:
                transformation = Transformation.objects.create(
                    transformation_date=t_date,
                    service_fee=batch_total_fee,
                    status=Transformation.Status.ACTIVE,
                    created_by=system_user,
                    updated_by=system_user,
                )
                transformations_created += 1

            except Exception as e:
                print(f"Failed to create Transformation header for {t_date}: {e}")
                continue

            for item_data in valid_rows_for_creation:
                row = item_data["data"]
                allocated_fee = item_data["fee"]

                engine_no = row.get("engine_number", "").strip()
                chassis_no = row.get("chassis_number", "").strip()
                model_name_csv = row.get("source_product", "").strip()

                if not engine_no or not chassis_no:
                    print(f"Skipping item: Missing engine or chassis number.")
                    items_skipped += 1
                    continue

                if not model_name_csv:
                    print(
                        f"Skipping item (Chassis: {chassis_no}): Missing model name (source_product)."
                    )
                    items_skipped += 1
                    continue

                try:
                    source_product = Product.objects.filter(
                        modelname__iexact=model_name_csv, type_variant="boxed"
                    ).first()

                    target_product = Product.objects.filter(
                        modelname__iexact=model_name_csv, type_variant="coupled"
                    ).first()

                    missing_variants = []
                    if not source_product:
                        missing_variants.append(f"'boxed' variant of {model_name_csv}")
                    if not target_product:
                        missing_variants.append(
                            f"'coupled' variant of {model_name_csv}"
                        )

                    if missing_variants:
                        print(
                            f"Product configuration error for Chassis {chassis_no}: Missing {', '.join(missing_variants)}. Skipping."
                        )
                        items_skipped += 1
                        continue

                except Exception as e:
                    print(f"Database Error looking up product '{model_name_csv}': {e}")
                    items_skipped += 1
                    continue

                try:
                    TransformationItem.objects.create(
                        transformation=transformation,
                        source_product=source_product,
                        target_product=target_product,
                        engine_number=engine_no,
                        chassis_number=chassis_no,
                        allocated_service_fee=allocated_fee,
                        status=TransformationItem.Status.AVAILABLE,
                        created_by=system_user,
                        updated_by=system_user,
                    )
                    items_created += 1
                except IntegrityError:
                    print(
                        f"Duplicate Entry: Engine {engine_no} or Chassis {chassis_no} already exists."
                    )
                    items_skipped += 1
                except Exception as e:
                    print(f"Error creating item {chassis_no}: {e}")
                    items_skipped += 1

    print("\n--- Import Summary ---")
    print(f"Transformation Headers Created: {transformations_created}")
    print(f"Transformation Items Created:   {items_created}")
    print(f"Items Skipped (Errors/Dupes):   {items_skipped}")
    print("-----------------------")
