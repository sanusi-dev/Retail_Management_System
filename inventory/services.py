import logging
from .models import *
from django.core.exceptions import ValidationError
from django.db import transaction
from core.utils import audit

logger = logging.getLogger(__name__)


class BusinessRuleViolation(Exception):
    pass


def process_transformation(form, formset, request):
    """
    Process a transformation: save items, decrement inventory, create transactions.
    """
    from utils.utils import create_inventory_transaction

    with transaction.atomic():
        transformation = form.save(commit=False)
        transformation.created_by = request.user
        transformation.updated_by = request.user
        transformation.save()

        items = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()

        service_fee_per_item = (
            transformation.service_fee / len(items) if len(items) > 0 else 0
        )
        for item in items:
            item.transformation = transformation
            source_product = item.source_product

            try:
                target_product = Product.objects.get(
                    base_product=source_product,
                    type_variant=Product.TypeVariant.COUPLED,
                )
                item.target_product = target_product
            except Product.DoesNotExist:
                raise ValidationError(
                    "Coupled variant not found for this Boxed product"
                )
            item.allocated_service_fee = service_fee_per_item
            item.unit_cost_at_transformation = (
                item.source_product.inventory.weighted_average_cost
                + service_fee_per_item
            )
            item.created_by = request.user
            item.updated_by = request.user
            item.save()

            # Decrement inventory (replaces update_inventory_and_create_transaction signal)
            inventory = Inventory.objects.select_for_update().get(
                product=item.source_product
            )
            if inventory.quantity < 1:
                raise BusinessRuleViolation("Insufficient Stock")

            inventory.quantity -= 1
            inventory.save(update_fields=["quantity", "updated_at"])

            create_inventory_transaction(
                inventory=inventory,
                source=item,
                transaction_type=InventoryTransaction.TransactionType.TRANSFORMATION,
                quantity_change=-1,
                cost_impact=inventory.weighted_average_cost,
            )


def can_void_transformation(transformation):
    if transformation.status == Transformation.Status.VOIDED:
        return False
    for item in transformation.transformation_items.all():
        if item.status != TransformationItem.Status.AVAILABLE:
            return False
    return True


def void_transformation(transformation_id, user, request=None):
    """
    Void a transformation: restore inventory for each item.
    Uses TransformationItem.create_reversal() which handles inventory restoration.
    """
    with transaction.atomic():
        transformation = (
            Transformation.objects.select_for_update()
            .select_related()
            .get(pk=transformation_id)
        )
        if not can_void_transformation(transformation):
            raise BusinessRuleViolation("This transformation cannot be voided — some items are not AVAILABLE.")

        for item in transformation.transformation_items.all():
            item.create_reversal()

        transformation.status = Transformation.Status.VOIDED
        transformation.save(update_fields=["status"])

        audit(user, 'void_transformation', transformation, detail={
            'transformation_number': transformation.transformation_number,
            'item_count': transformation.transformation_items.count(),
        }, request=request)

    return transformation


def void_and_correct(transformation_id):
    """Legacy wrapper — kept for backward compatibility."""
    return void_transformation(transformation_id, user=None)
