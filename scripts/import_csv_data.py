# import os
# import csv
# from django.conf import settings
# from customer.models import Customer


# def run():
#     file_path = os.path.join(settings.BASE_DIR, "csv_data", "transformation.csv")

#     if not os.path.exists(file_path):
#         print(f"Error: File not found at {file_path}")
#         return

#     with open(file_path, mode="r", encoding="utf-8") as f:
#         reader = csv.DictReader(f)

#         count = 0
#         skipped = 0

#         for row in reader:
#             name = row["name"].strip()
#             if not name:
#                 continue

#             # Check for existence to avoid IntegrityError on unique field
#             if Customer.objects.filter(full_name=name).exists():
#                 skipped += 1
#                 continue

#             try:
#                 Customer.objects.create(full_name=name)
#                 count += 1
#             except Exception as e:
#                 print(f"Failed to import {name}: {e}")

#         print(f"Import complete. Created: {count}, Skipped (Duplicate): {skipped}")
