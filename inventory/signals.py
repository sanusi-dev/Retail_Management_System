from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, Inventory


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
