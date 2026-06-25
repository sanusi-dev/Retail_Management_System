import logging

from django.db import DatabaseError, IntegrityError, OperationalError
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


def apply_sorting(queryset: QuerySet, sort_field: str, direction: str = 'asc', allowed_fields: list = None) -> QuerySet:
    """
    Applies sorting to a queryset based on the sort_field and direction.

    Args:
        queryset: The queryset to sort.
        sort_field: The field to sort by.
        direction: 'asc' for ascending, 'desc' for descending.
        allowed_fields: A list of allowed fields to sort by. If None, all fields are allowed (use with caution).

    Returns:
        The sorted queryset.
    """
    if not sort_field:
        return queryset

    clean_field = sort_field.lstrip("-")
    if allowed_fields and clean_field not in allowed_fields:
        return queryset

    if direction == "desc":
        sort_field = f"-{clean_field}"

    return queryset.order_by(sort_field)


def audit(user, action, obj, detail=None, request=None):
    """
    Call this explicitly inside service functions for auditable actions.
    Never call from signals.
    """
    from core.models import AuditLog

    try:
        ip = None
        if request:
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR')
        AuditLog.objects.create(
            user=user,
            action=action,
            object_type=type(obj).__name__,
            object_id=str(obj.pk),
            object_repr=str(obj),
            detail=detail or {},
            ip_address=ip,
        )
    except (DatabaseError, IntegrityError, OperationalError):
        logging.getLogger('core.audit').error(
            f"AuditLog failed: action={action}", exc_info=True
        )