from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid




class CustomUser(AbstractUser):
    pass

    def __str__(self):
        return self.username

# class Suppliers(models.Model):
#     supplier_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, primary_key=True)
#     name = models.CharField(max_length=255)
#     phone = models.CharField(max_length=50)
#     email = models.EmailField(null=True, blank=True, max_length=254)
#     address = models.TextField(null=True, blank=True)
#     created_by = models.ForeignKey(CustomUser, null=False, blank=False)
#     updated_by = models.ForeignKey(CustomUser, null=False, blank=False)


# class Products(models.Model):
#     CATEGORY = [
#         ('motorcycle', 'motorcycle'),
#         ('grinding_machine', 'grinding_machine'),
#         ('spare_parts', 'spare_parts')
#     ]
#     TYPE_VARIANTS = [
#         ('boxed', 'boxed'),
#         ('coupled', 'coupled')
#     ]
#     product_id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, unique=True)
#     sku = models.CharField(max_length=50, unique=True)
#     name = models.CharField(max_length=255)
#     category = models.CharField(choices=CATEGORY max_length=50)
#     type_variants = models.CharField(choices=TYPE_VARIANTS max_length=50)
#     description = models.TextField(blank=True, null=True)




