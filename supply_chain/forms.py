from django.forms import BaseModelFormSet, ModelForm
from django.forms.widgets import HiddenInput
from django.forms import modelformset_factory
from .models import *
from django.core.exceptions import ValidationError


class SupplierForm(ModelForm):
    class Meta:
        model = Supplier
        fields = ("name", "phone", "email", "address")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():

            if field_name == "address":
                field.widget.attrs["class"] = (
                    "block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-primary-500 focus:border-primary-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-primary-500 dark:focus:border-primary-500"
                )
                field.widget.attrs["placeholder"] = "Enter the supplier address..."
            else:
                field.widget.attrs["class"] = (
                    "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-primary-500 dark:focus:border-primary-500"
                )
                field.widget.attrs["placeholder"] = field_name


class PurchaseOrderForm(ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("supplier",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["supplier"].widget.attrs[
            "class"
        ] = "w-full p-2 border font-light rounded-l-md focus:outline-none focus:ring-1 focus:ring-blue-200"
        self.fields["supplier"].empty_label = "Select Supplier"


class PurchaseOrderItemForm(ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ("product", "ordered_quantity", "unit_price_at_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["product"].widget.attrs[
            "class"
        ] = "w-full p-1 focus:outline-none focus:ring-1 focus:ring-gray-100"
        self.fields["product"].empty_label = "Select Product"

        self.fields["ordered_quantity"].widget.attrs[
            "class"
        ] = "w-full p-1 focus:outline-none focus:ring-1 focus:ring-gray-100"
        self.fields["ordered_quantity"].widget.attrs["placeholder"] = "1"

        self.fields["unit_price_at_order"].widget.attrs[
            "class"
        ] = "w-full p-1 focus:outline-none focus:ring-1 focus:ring-gray-100"
        self.fields["unit_price_at_order"].widget.attrs["placeholder"] = "0.00"

    def clean(self):
        cleaned_data = super().clean()

        ordered_quantity = cleaned_data.get("ordered_quantity")
        unit_price_at_order = cleaned_data.get("unit_price_at_order")

        if ordered_quantity is None or ordered_quantity <= 0:
            raise ValidationError("Quantity must be greater than zero")

        if unit_price_at_order is None or unit_price_at_order <= 1000:
            raise ValidationError("Unit Price must be greater than 1,000")

        return cleaned_data


class PurchaseOrderItemFormset(BaseModelFormSet):

    def clean(self):
        super().clean()

        if any(self.errors):
            return
        products = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            product = form.cleaned_data.get("product")
            if product in products:
                raise ValidationError(
                    f"Duplicate product found: {product}. Each product can only appear once."
                )
            if product is not None:
                products.add(product)


PurchaseOrderItemFormSet = modelformset_factory(
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    formset=PurchaseOrderItemFormset,
    can_delete=True,
    extra=1,
)
