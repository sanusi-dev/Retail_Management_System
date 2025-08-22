from django.forms import BaseModelFormSet, ModelForm
from django.forms.widgets import HiddenInput
from django.forms import modelformset_factory
from .models import *
from django.core.exceptions import ValidationError
from django.db.models import Q


class SupplierForm(ModelForm):
    class Meta:
        model = Supplier
        fields = (
            "salutation",
            "firstname",
            "lastname",
            "company_name",
            "display_name",
            "email",
            "work_phone",
            "mobile",
            "address",
        )


class PurchaseOrderForm(ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ("supplier",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].empty_label = "Select Supplier"


class PurchaseOrderItemForm(ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ("product", "ordered_quantity", "unit_price_at_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].empty_label = "Click to select an item"


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
                    f"Duplicate item found '{product.modelname.upper()}'. Items must be distinct."
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
