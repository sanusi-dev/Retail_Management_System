import logging
from decimal import Decimal, ROUND_HALF_UP
from .models import *
from django.core.exceptions import ValidationError
from django.db import transaction
from core.utils import audit

logger = logging.getLogger(__name__)


class BusinessRuleViolation(Exception):
    pass


def _deplete_fifo_layers(product, quantity):
    """
    Deplete *quantity* units from the oldest FIFO cost layers for *product*.
    Returns a tuple of (total_cost, consumption_entries).

    Each consumption entry is a dict:
        {"layer": InventoryCostLayer, "quantity": int, "unit_cost": Decimal}

    If no FIFO layers exist (e.g. legacy inventory before FIFO was introduced),
    falls back to creating a synthetic layer using the current WAC.
    Must be called within a transaction that has already locked inventory.
    """
    from .models import InventoryCostLayer

    layers = (
        InventoryCostLayer.objects.filter(
            product=product,
            remaining_quantity__gt=0,
            is_voided=False,
        )
        .order_by("created_at")
        .select_for_update()
    )

    total_available = sum(l.remaining_quantity for l in layers)

    if total_available < quantity:
        # Fallback: no (or insufficient) FIFO layers — use current WAC for the gap
        inventory = product.inventory
        wac = inventory.weighted_average_cost
        if inventory.quantity < quantity:
            raise BusinessRuleViolation(
                f"Insufficient stock for {product.modelname}. "
                f"Requested: {quantity}, available: {inventory.quantity}."
            )

        gap = quantity - total_available
        # Create a synthetic layer for the uncovered portion (legacy inventory)
        InventoryCostLayer.objects.create(
            product=product,
            quantity=gap,
            remaining_quantity=gap,
            unit_cost=wac,
        )
        # Re-fetch layers to include the new synthetic one
        layers = (
            InventoryCostLayer.objects.filter(
                product=product,
                remaining_quantity__gt=0,
                is_voided=False,
            )
            .order_by("created_at")
            .select_for_update()
        )

    remaining_to_deplete = quantity
    total_cost = Decimal("0.00")
    consumption_entries = []

    for layer in layers:
        if remaining_to_deplete <= 0:
            break
        take = min(layer.remaining_quantity, remaining_to_deplete)
        layer.remaining_quantity -= take
        layer.save(update_fields=["remaining_quantity"])
        total_cost += Decimal(str(take)) * layer.unit_cost
        consumption_entries.append({
            "layer": layer,
            "quantity": take,
            "unit_cost": layer.unit_cost,
        })
        remaining_to_deplete -= take

    if remaining_to_deplete > 0:
        raise BusinessRuleViolation(
            f"Insufficient stock in FIFO layers for {product.modelname}. "
            f"Requested: {quantity}, available in layers: {quantity - remaining_to_deplete}."
        )

    return total_cost, consumption_entries


def _restore_fifo_layer(product, quantity, unit_cost):
    """
    Create a new FIFO cost layer (used when a sale or transformation is voided,
    returning units to inventory at their original cost).
    """
    from .models import InventoryCostLayer

    InventoryCostLayer.objects.create(
        product=product,
        quantity=quantity,
        remaining_quantity=quantity,
        unit_cost=unit_cost,
    )


def _recalculate_assembly_cost(target_product):
    """Recalculate assembly cost for a coupled product from its non-voided items."""
    from django.db.models import Sum

    items = target_product.transform_to.exclude(status=TransformationItem.Status.VOIDED)
    count = items.count()
    if count > 0:
        total = items.aggregate(total=Sum("unit_cost_at_transformation"))["total"] or 0
        target_product.assembly_cost = Decimal(str(total)) / count
    else:
        target_product.assembly_cost = Decimal("0.00")
    target_product.save(update_fields=["assembly_cost"])


def process_transformation(form, formset, request):
    """
    Process a transformation: save items, decrement inventory, create transactions.
    """
    from inventory.utils import create_inventory_transaction

    with transaction.atomic():
        transformation = form.save(commit=False)
        transformation.created_by = request.user
        transformation.updated_by = request.user
        transformation.save()

        items = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()

        n = len(items)
        if n > 0:
            raw_fee = transformation.service_fee / n
            service_fee_per_item = raw_fee.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            service_fee_per_item = Decimal("0.00")

        # Track which target products need assembly_cost recalculation
        target_products = set()

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


            # Decrement inventory first
            inventory = Inventory.objects.select_for_update().get(
                product=item.source_product
            )
            if inventory.quantity < 1:
                raise BusinessRuleViolation("Insufficient Stock")

            inventory.quantity -= 1
            inventory.save(update_fields=["quantity", "updated_at"])

            # FIFO depletion for the source product
            fifo_cost, consumptions = _deplete_fifo_layers(item.source_product, 1)
            item.unit_cost_at_transformation = fifo_cost + service_fee_per_item
            
            if consumptions:
                item.consumed_layer = consumptions[0]["layer"]
            item.created_by = request.user
            item.updated_by = request.user
            item.save()
            target_products.add(target_product)

            create_inventory_transaction(
                inventory=inventory,
                source=item,
                transaction_type=InventoryTransaction.TransactionType.TRANSFORMATION,
                quantity_change=-1,
                cost_impact=fifo_cost,
            )

        # Recalculate assembly cost for each affected coupled product
        for tp in target_products:
            _recalculate_assembly_cost(tp)
    return transformation


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

        target_products = set()
        for item in transformation.transformation_items.all():
            if item.target_product:
                target_products.add(item.target_product)
            item.create_reversal()
            # Legacy fallback: if consumed_layer was not tracked, create a new layer 
            if item.consumed_layer is None:
                source_unit_cost = max(Decimal("0.00"), item.unit_cost_at_transformation - item.allocated_service_fee)
                _restore_fifo_layer(item.source_product, 1, source_unit_cost)

        transformation.status = Transformation.Status.VOIDED
        transformation.save(update_fields=["status"])

        # Recalculate assembly cost for affected coupled products
        for tp in target_products:
            _recalculate_assembly_cost(tp)

        audit(user, 'void_transformation', transformation, detail={
            'transformation_number': transformation.transformation_number,
            'item_count': transformation.transformation_items.count(),
        }, request=request)

    return transformation


def void_and_correct(transformation_id):
    """Legacy wrapper — kept for backward compatibility."""
    return void_transformation(transformation_id, user=None)
