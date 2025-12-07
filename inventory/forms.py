from django import forms
from django.forms import ModelForm, modelformset_factory, BaseModelFormSet
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
            sku = f"{modelname}-{type_variant}"

            query = Product.objects.filter(sku=sku)
            if not self.instance._state.adding:
                query = query.exclude(pk=self.instance.pk)

            if query.exists():
                raise ValidationError(f"{sku} already exists.")

        return cleaned_data


class TransformationForm(ModelForm):
    class Meta:
        model = Transformation
        fields = (
            "service_fee",
            "transformation_date",
        )
        widgets = {
            "transformation_date": forms.DateInput(attrs={"type": "date"}),
        }


class TransformationItemForm(ModelForm):

    class Meta:
        model = TransformationItem
        fields = (
            "source_product",
            "engine_number",
            "chassis_number",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_product"].queryset = Product.objects.filter(
            type_variant=Product.TypeVariant.BOXED
        )
        self.fields["source_product"].empty_label = "Select a product to transform"


class BaseTransformationItemFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        engine_numbers = set()
        chassis_numbers = set()

        qs = TransformationItem.objects.all()
        inventory = Inventory.objects.select_related("product")
        consumption_demand = {inv.product: 0 for inv in inventory}
        inventory_lookup = {inv.product: inv for inv in inventory}

        db_engine_numbers = set(qs.values_list("engine_number", flat=True))
        db_chassis_numbers = set(qs.values_list("chassis_number", flat=True))

        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue

            source_product = form.cleaned_data.get("source_product")
            consumption_demand[source_product] += 1

            engine_number = form.cleaned_data.get("engine_number")
            chassis_number = form.cleaned_data.get("chassis_number")

            # Validate engine_number
            if engine_number:
                if engine_number in engine_numbers:
                    form.add_error(
                        "engine_number",
                        f"Engine number '{engine_number}' is duplicated within this form.",
                    )
                if engine_number in db_engine_numbers:
                    form.add_error(
                        "engine_number",
                        f"Engine number '{engine_number}' already exists in the system.",
                    )
                engine_numbers.add(engine_number)

            # Validate chassis_number
            if chassis_number:
                if chassis_number in chassis_numbers:
                    form.add_error(
                        "chassis_number",
                        f"Chassis number '{chassis_number}' is duplicated within this form.",
                    )
                if chassis_number in db_chassis_numbers:
                    form.add_error(
                        "chassis_number",
                        f"Chassis number '{chassis_number}' already exists in the system.",
                    )
                chassis_numbers.add(chassis_number)

            if chassis_number == engine_number:
                form.add_error(
                    "engine_number",
                    "Engine and chassis numbers must be different.",
                )

        # Validate available qty to transform
        for product, demanded_qty in consumption_demand.items():
            if demanded_qty == 0:
                continue  # skip unused products

            inv_record = inventory_lookup.get(product)
            if not inv_record:
                raise ValidationError(f"No inventory record for {product}")

            available_qty = inv_record.quantity
            if available_qty < demanded_qty:
                raise ValidationError(
                    f"Only {available_qty} of {product} is available for transformation."
                    if available_qty != 0
                    else f"There is no available quantity of {product} to transform"
                )


TransformationItemFormset = modelformset_factory(
    TransformationItem,
    form=TransformationItemForm,
    formset=BaseTransformationItemFormSet,
    can_delete=True,
    extra=1,
)
