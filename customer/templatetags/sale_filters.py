from django import template
from inventory.models import Product, TransformationItem
from customer.models import Customer

register = template.Library()


@register.filter
def product_display(product_id):
    """Return a display string for a product given its ID."""
    if not product_id:
        return ""
    try:
        product = Product.objects.select_related('brand').get(pk=product_id)
        brand_name = product.brand.name if product.brand else ""
        return f"{brand_name} {product.modelname}".strip()
    except Product.DoesNotExist:
        return ""


@register.filter
def transformation_item_display(item_id):
    """Return a display string for a transformation item given its ID."""
    if not item_id:
        return ""
    try:
        item = TransformationItem.objects.select_related('target_product').get(pk=item_id)
        model_name = item.target_product.modelname if item.target_product else ""
        return f"{item.item_number} - {model_name}".strip()
    except TransformationItem.DoesNotExist:
        return ""


@register.filter
def customer_display(customer_id):
    """Return a display string for a customer given their ID."""
    if not customer_id:
        return ""
    try:
        customer = Customer.objects.get(pk=customer_id)
        return customer.full_name
    except Customer.DoesNotExist:
        return ""
