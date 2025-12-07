# from inventory.models import *
# from supply_chain.models import PurchaseOrder
# from django.shortcuts import get_object_or_404
# from django.db.models import Sum
# from django.apps import apps
# from django.contrib.contenttypes.models import ContentType
# from easyaudit.models import CRUDEvent


# def run():
#     inventories = Inventory.objects.all().order_by("created_at")[:10]
#     inventory_dict = {}
#     for inventory in inventories:
#         inventory_dict[inventory] = 0
#     #  print(inventory_dict)

#     for source_product, qty in inventory_dict.items():
#         for product in inventories:
#             if product == source_product:
#                 import random

#                 inventory_dict[product] += random.randint(1, 100)
#                 print(f"{product}: {product.quantity_on_hand}")
#                 print(f"{source_product}: {qty}")

#     print(inventory_dict)
