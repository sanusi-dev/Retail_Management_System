from django.db import models
from account.models import CustomUser
import uuid


class Brand(models.Model):
    brand_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    CATEGORY = ['motorcycle', 'engine']
    TYPE_VARIANT = ['boxed', 'coupled', 'spare part']

    product_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    sku = models.CharField(max_length=50, blank=True, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='product')
    modelname = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY)
    type_variant = models.CharField(max_length=20, choices=TYPE_VARIANT)
    description = models.TextField(default='', blank=True)
    base_product = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='variants', help_text="Parent product if this is a variant")
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.modelname


class Inventory(models.Model):
    inventory_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='inventories')
    quantity_on_hand = models.IntegerField(max_length=20)
    last_updated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.product.modelname


class SerializedInventory(models.Model):
    STATUS = ['available', 'sold', 'reserved', 'damaged']

    serial_item_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='serialized_products')
    engine_number = models.CharField(max_length=255, unique=True)
    chassis_number = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS, default='active', blank=True)
    received_date = models.DateTimeField(auto_now_add=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

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
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.transformation_id