from django import template
from django.contrib.contenttypes.models import ContentType

register = template.Library()


@register.filter()
def get_field_from_event(crud_event, field_name):
    """Template filter to extract field values from CRUDEvent objects."""
    try:
        obj = crud_event.content_type.get_object_for_this_type(pk=crud_event.object_id)
        for part in field_name.split("."):
            obj = getattr(obj, part)
        return obj
    except Exception:
        return "obj not found"