from .models import *
from django.core.exceptions import ValidationError
from django.db import transaction


def process_transformation(form, formset, request):
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


def can_void_transformation(transformation):
    if transformation.status == Transformation.Status.VOIDED:
        return False
    for item in transformation.transformation_items.all():
        if item.status != TransformationItem.Status.AVAILABLE:
            return False

    return True


def void_and_correct(transformation_id):
    with transaction.atomic():
        transformation = (
            Transformation.objects.select_for_update()
            .select_related()
            .get(pk=transformation_id)
        )
        if not can_void_transformation(transformation):
            raise ValueError("This is transformation can not be voided")
        for item in transformation.transformation_items.all():
            item.create_reversal()

    transformation.status = Transformation.Status.VOIDED
    transformation.save(update_fields=["status"])
