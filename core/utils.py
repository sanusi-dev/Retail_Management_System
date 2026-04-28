import logging

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

    if allowed_fields and sort_field not in allowed_fields:
        return queryset

    if direction == 'desc':
        sort_field = f'-{sort_field}'

    return queryset.order_by(sort_field)


def apply_filtering(queryset: QuerySet, filter_params: dict, allowed_filters: list = None) -> QuerySet:
    """
    Applies filtering to a queryset.

    Args:
        queryset: The queryset to filter.
        filter_params: A dictionary of filter parameters (e.g., request.GET).
        allowed_filters: A list of allowed filter keys.

    Returns:
        The filtered queryset.
    """
    if not filter_params:
        return queryset

    filters = {}
    for key, value in filter_params.items():
        if allowed_filters and key in allowed_filters and value:
            filters[key] = value

    if filters:
        queryset = queryset.filter(**filters)

    return queryset


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
    except Exception:
        logging.getLogger('core.audit').error(
            f"AuditLog failed: action={action}", exc_info=True
        )