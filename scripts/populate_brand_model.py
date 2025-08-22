from inventory.models import Brand
from supply_chain.models import *
from account.models import CustomUser
from django.utils import timezone


def populate_brand_model():
    brand_name = [
        "Bajaj",
        "Hero",
        "Honda",
        "Qlink",
        "Sinoki",
        "Suzuki",
        "TVS",
        "Yamaha",
        "Kasea",
        "Qingqi",
        "Lifan",
        "Kavaki",
        "Haojue",
    ]
    user = CustomUser.objects.first()
    brand_data = [
        {
            "name": i,
            "created_at": timezone.now(),
            "updated_at": timezone.now(),
            "created_by": user,
            "updated_by": user,
        }
        for i in brand_name
    ]

    Brand.objects.bulk_create([Brand(**data) for data in brand_data])
