from inventory.models import Product, Brand
from supply_chain.models import *
from django.contrib.auth import get_user_model
import random


def populate_product_model():
    # --- Step 1: Fetch existing user and brands ---
    try:
        CustomUser = get_user_model()
        user = CustomUser.objects.first()
        if not user:
            print("Error: No users found. Please create a user first.")
            return

        all_brands = {brand.name: brand for brand in Brand.objects.all()}
        if not all_brands:
            print(
                "Error: No brands found. Please add the required brands to the database."
            )
            return

        print(f"Found {len(all_brands)} existing brands and one user.")
    except Exception as e:
        print(f"Error fetching user/brands: {e}")
        return

    # --- Step 2: Define structured product data for brand-model matching ---
    brand_model_map = {
        "Bajaj": ["Boxer CT100", "Pulsar 150"],
        "Honda": ["CGL125", "CB150F"],
        "Yamaha": ["YBR125", "MT15"],
        "Suzuki": ["GIXXER 155"],
        "Hero": ["Glamour 125"],
        "Kavaki": ["KAVAKI-R15"],
        "Haojue": ["HJ150-10"],
    }

    engine_models = ["Grinder-E150cc", "Grinder-E125cc"]
    spare_part_models = ["Front-Tyre-3.00", "Rear-Tyre-3.50"]

    products_to_create = []
    base_motorcycles = []

    # --- Step 3: Create 5 ENGINE and 5 SPARE_PART products (10 total) ---
    engine_brands = [
        all_brands.get(brand_name)
        for brand_name in ["Yamaha", "Honda"]
        if all_brands.get(brand_name)
    ]
    if not engine_brands:
        print(
            "Required brands for engines (Yamaha, Honda) not found. Skipping engine creation."
        )

    for i in range(5):
        if not engine_brands:
            break
        brand = random.choice(engine_brands)
        modelname = f"{random.choice(engine_models)}-{i+1}"
        category = Product.Category.ENGINE
        type_variant = Product.TypeVariant.BOXED
        sku = (
            f"{modelname.lower().replace(' ', '')}-{brand.name.lower()}-{type_variant}"
        )

        products_to_create.append(
            Product(
                sku=sku,
                brand=brand,
                modelname=modelname,
                category=category,
                type_variant=type_variant,
                description=f"Grinding machine engine, model {modelname}.",
                created_by=user,
                updated_by=user,
            )
        )

    # Create 5 Spare Part products (all are BOXED)
    spare_part_brands = [
        all_brands.get(brand_name)
        for brand_name in ["Bajaj", "TVS"]
        if all_brands.get(brand_name)
    ]
    if not spare_part_brands:
        print(
            "Required brands for spare parts (Bajaj, TVS) not found. Skipping spare parts creation."
        )

    for i in range(5):
        if not spare_part_brands:
            break
        brand = random.choice(spare_part_brands)
        modelname = f"{random.choice(spare_part_models)}-{i+1}"
        category = Product.Category.SPARE_PART
        type_variant = Product.TypeVariant.BOXED
        sku = (
            f"{modelname.lower().replace(' ', '')}-{brand.name.lower()}-{type_variant}"
        )

        products_to_create.append(
            Product(
                sku=sku,
                brand=brand,
                modelname=modelname,
                category=category,
                type_variant=type_variant,
                description=f"A new tire for a motorcycle, model {modelname}.",
                created_by=user,
                updated_by=user,
            )
        )

    # --- Step 4: Create 20 MOTORCYCLE products (10 boxed, 10 coupled) ---
    all_motorcycle_models = [
        (brand_name, model_name)
        for brand_name, models in brand_model_map.items()
        for model_name in models
    ]

    # Shuffle the list to get 10 unique motorcycle models for base products
    random.shuffle(all_motorcycle_models)

    # Create 10 base (boxed) motorcycle products
    for brand_name, modelname in all_motorcycle_models[:10]:
        brand = all_brands.get(brand_name)
        if not brand:
            continue

        category = Product.Category.MOTORCYCLE
        type_variant = Product.TypeVariant.BOXED
        sku = (
            f"{modelname.lower().replace(' ', '')}-{brand.name.lower()}-{type_variant}"
        )

        new_product = Product(
            sku=sku,
            brand=brand,
            modelname=modelname,
            category=category,
            type_variant=type_variant,
            description=f"A new boxed motorcycle, model {modelname}.",
            created_by=user,
            updated_by=user,
        )
        products_to_create.append(new_product)
        base_motorcycles.append(new_product)

    # Create 10 coupled variants, one for each base motorcycle
    for base_prod in base_motorcycles:
        type_variant = Product.TypeVariant.COUPLED
        sku = f"{base_prod.modelname.lower().replace(' ', '')}-{base_prod.brand.name.lower()}-{type_variant}"

        variant_product = Product(
            sku=sku,
            brand=base_prod.brand,
            modelname=f"{base_prod.modelname}-Coupled",
            category=base_prod.category,
            type_variant=type_variant,
            description=f"Coupled variant of {base_prod.modelname}.",
            base_product=base_prod,
            created_by=user,
            updated_by=user,
        )
        products_to_create.append(variant_product)

    # --- Step 5: Bulk create the products for efficiency ---
    if products_to_create:
        Product.objects.bulk_create(products_to_create)
        print(f"Successfully created {len(products_to_create)} product records.")
    else:
        print("No products to create.")


def get_child_accessors(parent_model):
    """
    Returns a list of all related managers (child accessors) for a given model.
    """
    related_fields = [
        f
        for f in parent_model._meta.get_fields()
        if (f.one_to_many or f.one_to_one) and f.auto_created
    ]
    return [f.get_accessor_name() for f in related_fields]
