from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .models import Product, Inventory
from account.models import CustomUser


@receiver(post_save, sender=Product)
def create_product_inventory(sender, instance, created, **kwargs):
    """Create inventory record when a new product is created"""
    if created and not instance.base_product:
        Inventory.objects.create(
            product=instance,
            created_by=instance.created_by,
            updated_by=instance.updated_by,
            quantity_on_hand=0,
        )


# @receiver(pre_save, sender=Product)
# def product_pre_save(sender, instance, **kwargs):
#     """Do something before product is saved"""
#     # Example: Auto-generate SKU or slug
#     if not instance.sku:
#         instance.sku = f"PRD-{instance.modelname[:3].upper()}-{instance.pk or 'NEW'}"


# @receiver(post_delete, sender=Product)
# def product_deleted(sender, instance, **kwargs):
#     """Clean up when product is deleted"""
#     # Log the deletion or perform cleanup
#     print(f"Product {instance.modelname} was deleted")


# @receiver(post_save, sender=PurchaseOrder)
# def update_inventory_on_delivery(sender, instance, created, **kwargs):
#     """Update inventory when purchase order status changes"""
#     if instance.status == "delivered" and not created:
#         # Update inventory quantities
#         for item in instance.items.all():
#             inventory = item.product.inventory
#             inventory.quantity_on_hand += item.quantity
#             inventory.save()
