from django.db import models
from account.models import CustomUser
import uuid
from django.db.models import Q, CheckConstraint, F
from django.utils import timezone

from customer.models import Customer, Sale


class Customer(models.Model):
    pass

class Sale(models.Model):
    pass