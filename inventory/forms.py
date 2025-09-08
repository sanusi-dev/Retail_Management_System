from django import forms
from .models import *
from django.core.exceptions import ValidationError
from django.forms.widgets import RadioSelect


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "modelname",
            "brand",
            "category",
            "description",
        ]
        widgets = {"type_variant": RadioSelect()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["brand"].empty_label = "Select brand"

    def clean(self):
        cleaned_data = super().clean()

        modelname = cleaned_data.get("modelname")
        brand = cleaned_data.get("brand")
        type_variant = self.instance.type_variant

        if modelname and brand and type_variant:
            sku = f"{str(brand)}-{modelname}-{type_variant}"

            query = Product.objects.filter(sku=sku)
            if not self.instance._state.adding:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise ValidationError(
                    f'The product combination of "{brand}", "{modelname}", and "{type_variant}" already exists.'
                )

        return cleaned_data
