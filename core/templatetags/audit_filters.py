from decimal import Decimal

from django import template

register = template.Library()

KEY_LABELS = {
    "void_reason": "Reason",
    "reason": "Reason",
    "amount": "Amount",
    "total": "Total",
    "amount_allocated": "Allocated",
    "cfa_amount": "CFA Amount",
    "old_quantity": "Old Qty",
    "new_quantity": "New Qty",
    "old_price": "Old Price",
    "new_price": "New Price",
    "allocation_increase": "Allocation Change",
    "old_version": "Old Ver",
    "new_version": "New Ver",
    "line_number": "Line",
    "agreement_number": "Agreement",
    "cfa_agreement_number": "CFA Agreement",
    "fulfillment_number": "Fulfillment",
    "gr_number": "Receipt",
    "po_number": "PO",
    "transformation_number": "Transformation",
    "item_count": "Items",
    "account_id": "Account",
    "cfa_agreement_id": "CFA ID",
    "payment_method": "Payment",
}
MONETARY_KEYS = frozenset({
    "amount", "total", "amount_allocated", "cfa_amount",
    "old_price", "new_price", "allocation_increase",
})


@register.filter
def audit_badge_class(action: str) -> str:
    if not action:
        return "badge-pending"
    action_lower = action.lower()
    if "void" in action_lower:
        return "badge-voided"
    if "cancel" in action_lower:
        return "badge-partial"
    if "create" in action_lower or "record" in action_lower:
        return "badge-active"
    return "badge-pending"


@register.filter
def format_audit_detail(detail: dict, action: str = "") -> str:
    if not detail:
        return ""

    parts = []

    for key, label in KEY_LABELS.items():
        value = detail.get(key)
        if value is None or value == "":
            continue

        if key in MONETARY_KEYS:
            try:
                formatted = f"₦{Decimal(str(value)):,.0f}"
            except (ValueError,):
                formatted = f"₦{value}"
            parts.append(f"{label}: {formatted}")
        else:
            parts.append(f"{label}: {value}")

    if not parts:
        return str(detail)

    return "  ·  ".join(parts)
