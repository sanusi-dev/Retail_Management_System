from inventory.models import Product
from django.shortcuts import get_object_or_404
from django.db.models import Sum



def run():
    Product.objects.all().update(status=Product.Status.ACTIVE)

#     for p in product:
#         p.status = product.Status.ACTIVE

#         product.save()
    






    # def total_remaining_qty(self):
    #     annotated = self.po_items.annotate(
    #         total_received=Sum("receipt_items__received_quantity")
    #     ).annotate(remaining_calc=F("ordered_quantity") - F("total_received"))
    #     remaining_calc = annotated.aggregate(total=Sum("remaining_calc"))["total"]
    #     return remaining_calc or 0
