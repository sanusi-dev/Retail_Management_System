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
            "type_variant",
            "base_product",
            "description",
        ]
        widgets = {"type_variant": RadioSelect()}


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["brand"].empty_label = "Select brand"
        self.fields["base_product"].empty_label = "Select parent"
        self.fields["base_product"].queryset = Product.objects.exclude(
            type_variant="coupled"
        )

        if not self.instance._state.adding:
            print(self.instance.receipt_items.all())
            for related in self.instance._meta.related_objects:
                manager = getattr(self.instance, related.get_accessor_name())
                if manager.exists():
                    self.fields["type_variant"].disabled = True
                    self.fields["base_product"].disabled = True


    def clean(self):
        cleaned_data = super().clean()

        modelname = cleaned_data.get("modelname")
        brand = cleaned_data.get("brand")
        type_variant = cleaned_data.get("type_variant")
        base_product = cleaned_data.get("base_product")

        if modelname and brand and type_variant:
            sku = f"{str(brand)}-{modelname}-{type_variant}"

            query = Product.objects.filter(sku=sku)
            if not self.instance._state.adding:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise ValidationError(
                    f'The product combination of "{brand}", "{modelname}", and "{type_variant}" already exists.'
                )

        if type_variant == "boxed" and base_product:
            raise ValidationError(
                "Boxed product does not need a parent, Base Product field should be empty"
            )

        elif type_variant == "coupled" and not base_product:
            raise ValidationError(
                "Coupled product type need a parent, Base Product field should not be empty"
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if instance.modelname and instance.brand and instance.type_variant:
            sku = f"{str(instance.brand)}-{instance.modelname}-{instance.type_variant}"
            instance.sku = sku

        if commit:
            instance.save()

        return instance
