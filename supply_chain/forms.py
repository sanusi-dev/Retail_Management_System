from django.forms import BaseModelFormSet, ModelForm
from django.shortcuts import get_object_or_404
from django import forms
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
        fields = ("supplier", "order_date", "shipping_cost")
        widgets = {
            "order_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["supplier"].empty_label = "Select Supplier"


class PurchaseOrderItemForm(ModelForm):

    class Meta:
        model = PurchaseOrderItem
        fields = ("product", "ordered_quantity", "unit_price_at_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].empty_label = "Select an item"
        self.fields["product"].queryset = Product.objects.filter(
            type_variant=Product.TypeVariant.BOXED
        )


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


class PaymentForm(ModelForm):
    class Meta:
        model = Payment
        fields = (
            "purchase_order",
            "amount_paid",
            "payment_date",
            "payment_method",
            "remark",
        )
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].empty_label = "Select purchase order"
        self.fields["purchase_order"].queryset = PurchaseOrder.objects.exclude(
            payment_status="fulfilled"
        )

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount_paid")
        purchase_order = cleaned_data.get("purchase_order")

        purchase_order = get_object_or_404(PurchaseOrder, pk=purchase_order.pk)
        remaining_balance = (
            purchase_order.total_amount - purchase_order.total_payment_made
        )
        if amount > remaining_balance:
            raise forms.ValidationError(
                f"Amount exceeds the remaining balance for this PO. Remaining Bal: {remaining_balance:,.2f}"
            )

        return cleaned_data


class GoodsReceiptForm(ModelForm):
    class Meta:
        model = GoodsReceipt
        fields = ("purchase_order", "delivery_date")
        widgets = {
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].empty_label = "Select a Purchase Order"
        self.fields["purchase_order"].queryset = PurchaseOrder.objects.exclude(
            delivery_status="received"
        )
        if self.instance and not self.instance._state.adding:
            self.fields["purchase_order"].disabled = True


class GoodsReceiptItemForm(ModelForm):
    class Meta:
        model = GoodsReceiptItem
        fields = ("purchase_order_item", "product", "received_quantity")
        widgets = {
            "product": forms.HiddenInput(),
            "purchase_order_item": forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        po_item = cleaned_data.get("purchase_order_item")
        received_quantity = cleaned_data.get("received_quantity")

        original_received = self.instance.received_quantity

        if po_item and received_quantity is not None:
            total_remaining = po_item.remaining_qty
            if received_quantity > total_remaining + original_received:
                self.add_error(
                    "received_quantity",
                    f"Quantity cannot exceed the remaining amount to receive ({po_item.ordered_quantity}).",
                )

        return cleaned_data


GoodsReceiptItemFormset = modelformset_factory(
    GoodsReceiptItem,
    form=GoodsReceiptItemForm,
    can_delete=True,
    extra=0,
)
