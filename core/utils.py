from django.db.models import QuerySet

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
