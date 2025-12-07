from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from .models import *
from . import services
from django.db import transaction


@receiver(post_save, sender=Product)
def create_coupled_product(sender, instance, created, **kwargs):
    """Create coupled product after boxed product is created"""
    if (
        created
        and not instance.base_product
        and instance.category == Product.Category.MOTORCYCLE
    ):
        Product.objects.create(
            brand=instance.brand,
            modelname=instance.modelname,
            category=instance.category,
            type_variant=instance.TypeVariant.COUPLED,
            base_product=instance,
            created_by=instance.created_by,
            updated_by=instance.updated_by,
        )


@receiver(post_save, sender=Product)
def create_product_inventory(sender, instance, created, **kwargs):
    """Create inventory record when a new product is created"""
    if created and not instance.base_product:
        Inventory.objects.create(
            product=instance,
            created_by=instance.created_by,
            updated_by=instance.updated_by,
        )


@receiver(post_save, sender=TransformationItem)
def update_inventory_and_create_transaction(sender, instance, created, **kwargs):
    if not created:
        return

    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(
            product=instance.source_product
        )
        if inventory.quantity < 1:
            raise ValueError("Insufficient Stock")

        inventory.quantity -= 1
        inventory.save(update_fields=["quantity"])

        services.create_inventory_transaction(
            inventory=inventory,
            source=instance,
            transaction_type=InventoryTransaction.TransactionType.TRANSFORMATION,
            quantity_change=-1,
            cost_impact=inventory.weighted_average_cost,
        )
