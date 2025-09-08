from django import template

register = template.Library()


@register.filter()
def status_color(status_string):
    CHOICE_COLOR_MAP = {
        # General Statuses
        "active": "text-green-700",
        "inactive": "text-red-700",
        "available": "text-green-700",
        "sold": "text-gray-700",
        "damaged": "text-red-700",
        "completed": "text-green-700",
        "reversed": "text-yellow-700",
        # Product Variants
        "boxed": "text-gray-700",
        "coupled": "text-blue-700",
        # Purchase Order Lifecycle
        "draft": "text-gray-700",
        "open": "text-blue-700",
        "partially received": "text-yellow-700",
        "fully received": "text-green-700",
        "cancelled": "text-red-700",
        "closed": "text-gray-700",
        # Goods Receipt
        "submitted": "text-green-700",
        "pending": "text-yellow-700",
        "received": "text-green-700",
        # Supplier Payment
        "fulfilled": "text-green-700",
        "voided": "text-red-700",
        # Payment Methods (Neutral)
        "bank transfer": "text-gray-700",
        "cash": "text-gray-700",
        "check": "text-gray-700",
        "other": "text-gray-700",
        # Default fallback
        "default": "text-gray-700",
    }
    return CHOICE_COLOR_MAP.get(str(status_string).lower(), CHOICE_COLOR_MAP["default"])
