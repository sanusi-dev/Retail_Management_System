from inventory.models import Product, Brand, Inventory
from django.contrib.auth import get_user_model
import random

def run():
    # --- Step 1: Fetch existing user and brands ---
    try:
        CustomUser = get_user_model()
        user = CustomUser.objects.first()
        if not user:
            print("Error: No users found. Please create a user first.")
            return

        brands = list(Brand.objects.all())
        if not brands:
            print("Error: No brands found. Please add at least one brand.")
            return

        print(f"Found {len(brands)} existing brands and one user.")
    except Exception as e:
        print(f"Error fetching user/brands: {e}")
        return

    # --- Step 2: Prepare for bulk creation ---
    products_to_create = []
    total_products = 500

    print(f"Preparing to create {total_products} boxed motorcycle products...")

    # Find the highest number used in a modelname to avoid collisions
    # This is more complex now, so we query all products
    existing_model_nums = set()
    all_products = Product.objects.values_list('modelname', flat=True)
    for name in all_products:
        try:
            # Extracts the number from 'baj125' -> 125
            num_part = ''.join(filter(str.isdigit, name))
            if num_part:
                existing_model_nums.add(int(num_part))
        except (ValueError, IndexError):
            continue
    
    start_index = max(existing_model_nums) if existing_model_nums else 100

    for i in range(total_products):
        brand = random.choice(brands)
        
        # Create modelname like 'baj125', 'hon126'
        prefix = brand.name[:3].lower()
        model_index = start_index + i + 1
        modelname = f"{prefix}{model_index}"

        category = Product.Category.MOTORCYCLE
        type_variant = Product.TypeVariant.BOXED

        # SKU is auto-generated on save, but we can create a placeholder
        sku = f"{brand.name}-{modelname}-{type_variant}".upper().replace(' ', '')

        products_to_create.append(
            Product(
                sku=sku,
                brand=brand,
                modelname=modelname,
                category=category,
                type_variant=type_variant,
                description=f"A new boxed motorcycle, model {modelname}.",
                created_by=user,
                updated_by=user,
            )
        )

    # --- Step 3: Bulk create the products and inventory for efficiency ---
    if products_to_create:
        # Bulk create products
        created_products = Product.objects.bulk_create(products_to_create)
        print(f"Successfully created {len(created_products)} product records.")

        # Prepare inventory records for the newly created products
        inventory_records = []
        for product in created_products:
            inventory_records.append(
                Inventory(
                    product=product,
                    quantity_on_hand=0, # Start with 0 quantity
                    created_by=user,
                    updated_by=user,
                )
            )

        # Bulk create inventory records
        Inventory.objects.bulk_create(inventory_records)
        print(f"Successfully created {len(inventory_records)} inventory records.")
    else:
        print("No products to create.")

    print("Script finished.")