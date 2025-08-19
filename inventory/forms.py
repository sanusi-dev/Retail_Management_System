from django import forms
from .models import *
from django.core.exceptions import ValidationError



class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'modelname',
            'brand',
            'category',
            'type_variant',
            'base_product',
            'description',
            'is_active',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # this is to not display the is_active field when creating
        if not (self.instance and self.instance.pk):
            del self.fields['is_active']

        self.fields['brand'].empty_label = 'Select brand...'
        self.fields['base_product'].empty_label = 'Select parent if coupled...'

        for field_name, field in self.fields.items():
            
            if field_name == 'description':
                field.widget.attrs['class'] = "block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-primary-500 dark:focus:border-primary-500"
                field.widget.attrs['placeholder'] = 'Enter a description for the product...'
            elif field_name == 'is_active':
                field.widget.attrs['class'] = "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                field.widget.attrs['type'] = 'radio'
            else:
                field.widget.attrs['class'] = "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-primary-500 dark:focus:border-primary-500"
                field.widget.attrs['placeholder'] = 'e.g., CGL 125'

    def clean(self):
        cleaned_data =  super().clean()

        modelname = cleaned_data.get('modelname')
        brand = cleaned_data.get('brand')
        type_variant = cleaned_data.get('type_variant')
        base_product = cleaned_data.get('base_product')

        if modelname and brand and type_variant:
            sku = f"{str(brand)}-{modelname}-{type_variant}"

            query = Product.objects.filter(sku=sku)
            if self.instance.pk:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise ValidationError(
                    f'The product combination of "{brand}", "{modelname}", and "{type_variant}" already exists.'
                )
            
        if type_variant == 'boxed' and base_product:
            raise ValidationError(
                "Boxed product does not need a parent, Base Product field should be empty"
            )
        
        elif type_variant == 'coupled' and not base_product:
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


