from django.forms import Select


class Select2Widget(Select):
    def __init__(self, attrs=None, **kwargs):
        default_attrs = {"class": "select2-enabled"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs, **kwargs)
