from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import (
    Customer,
    DepositAccount,
    PurchaseAgreement,
    BoxedSale,
    CoupledSale,
)
from inventory.models import TransformationItem, Inventory, InventoryTransaction
from inventory.utils import create_inventory_transaction


# ========================================================================
# SIGNALS THAT STAY (simple auto-creation hooks, no financial logic)
# ========================================================================


@receiver(post_save, sender=Customer)
def create_deposit_account(sender, instance, created, **kwargs):
    """Automatically create a deposit account when a customer is created."""
    if created:
        DepositAccount.objects.create(
            customer=instance,
            created_by=instance.created_by,
            updated_by=instance.updated_by,
        )


@receiver(pre_delete, sender=PurchaseAgreement)
def prevent_deletion_of_fulfilled_agreements(sender, instance, **kwargs):
    if instance.agreement_sales.exists():
        raise ValidationError(
            "Cannot delete a Purchase Agreement that already has linked Sales. "
            "Void the sales first."
        )


# ========================================================================
# SIGNALS THAT STAY (admin deletion safety nets)
# These handle inventory restoration when items are deleted via Django admin.
# ========================================================================


@receiver(post_delete, sender=BoxedSale)
def return_inventory_on_sale_deletion(sender, instance, **kwargs):
    """Return stock if a BoxedSale is manually deleted via Admin."""
    with transaction.atomic():
        inventory = Inventory.objects.select_for_update().get(product=instance.product)
        inventory.quantity += instance.quantity
        inventory.save(update_fields=["quantity"])

        consumptions = instance.layer_consumptions.all()
        if consumptions.exists():
            reversal_cost = Decimal("0.00")
            for c in consumptions:
                c.cost_layer.remaining_quantity += c.quantity_consumed
                c.cost_layer.save(update_fields=["remaining_quantity"])
                reversal_cost += Decimal(str(c.quantity_consumed)) * c.unit_cost
        elif instance.cost_basis is not None:
            from inventory.services import _restore_fifo_layer
            reversal_cost = instance.cost_basis
            unit_cost = instance.cost_basis / instance.quantity
            _restore_fifo_layer(instance.product, instance.quantity, unit_cost)
        else:
            reversal_cost = inventory.weighted_average_cost * instance.quantity

        create_inventory_transaction(
            inventory=inventory,
            source=instance,
            transaction_type=InventoryTransaction.TransactionType.SALE_REVERSAL,
            quantity_change=instance.quantity,
            cost_impact=reversal_cost,
        )


@receiver(post_delete, sender=CoupledSale)
def mark_item_available(sender, instance, **kwargs):
    """Make item available again if CoupledSale is manually deleted."""
    with transaction.atomic():
        TransformationItem.objects.select_for_update().filter(
            pk=instance.transformation_item.pk
        ).update(status=TransformationItem.Status.AVAILABLE)
