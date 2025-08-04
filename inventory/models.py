from django.db import models
from account.models import CustomUser
import uuid


class Brand(models.Model):
    brand_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    class Category(models.TextChoices):
        MOTORCYCLE = 'motorcycle', 'Motorcycle'
        ENGINE = 'engine', 'Engine'

    class TypeVariant(models.TextChoices):
        BOXED = 'boxed', 'Boxed'
        COUPLED = 'coupled', 'Coupled'
        SPARE_PART = 'spare part', 'Spare Part'

    product_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sku = models.CharField(max_length=50, blank=True, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='product')
    modelname = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category)
    type_variant = models.CharField(max_length=20, choices=TypeVariant)
    description = models.TextField(default='', blank=True)
    base_product = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='variants', help_text="Parent product if this is a variant")
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.modelname


class Inventory(models.Model):
    inventory_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='inventories')
    quantity_on_hand = models.IntegerField()
    last_updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.product.modelname


class SerializedInventory(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        SOLD = 'sold', 'Sold'
        RESERVED = 'reserved', 'Reserved'
        DAMAGED = 'damaged', 'Damaged'

    serial_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='serialized_products')
    engine_number = models.CharField(max_length=255, unique=True)
    chassis_number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.AVAILABLE, blank=True)
    received_date = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.product.modelname
    

class InventoryTransformation(models.Model):
    transformation_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    boxed_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='boxed_products')
    coupled_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='coupled_products')
    engine_number = models.CharField(max_length=255, unique=True)
    chassis_number = models.CharField(max_length=255, unique=True)
    transformation_date = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='created_%(class)s_set')
    updated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, blank=True, null=True, related_name='updated_%(class)s_set')

    def __str__(self):
        return self.transformation_id