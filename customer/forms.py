from django import forms
from .models import (
    Customer,
    Transaction,
    DepositAccount,
    PurchaseAgreement,
    PurchaseAgreementLineItem,
    CfaAgreement,
    CfaFulfillment,
    Sale,
    CoupledSale,
    BoxedSale,
)
from inventory.models import Product, TransformationItem, Inventory
from django.forms import BaseInlineFormSet
from django.db.models import Sum, F, Q
from decimal import Decimal
from django.utils import timezone
from django.forms import inlineformset_factory


from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)


class CustomerForm(forms.ModelForm):

    class Meta:
        model = Customer
        fields = (
            "full_name",
            "phone",
            "email",
            "address",
        )


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["account", "transaction_type", "amount", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.initial.get("account"):
            target_account = self.initial.get("account")
            self.fields["account"].queryset = DepositAccount.objects.filter(
                pk=target_account.pk
            )
            self.fields["account"].empty_label = None

        else:
            self.fields["account"].empty_label = "Select an account"

        if self.initial.get("transaction_type"):
            target_trxn_type = self.initial.get("transaction_type")
            try:
                trxn_enum = Transaction.TransactionType(target_trxn_type.lower())
                self.fields["transaction_type"].choices = [
                    (trxn_enum.value, trxn_enum.label),
                ]

            except ValueError as e:
                error_message = (
                    f"Invalid initial transaction type '{target_trxn_type}' provided. "
                    f"Falling back to default choices. Error: {e}"
                )
                logger.warning(error_message, exc_info=True)
                self.set_default_choices()

        else:
            self.set_default_choices()

    def set_default_choices(self):
        """Helper to set default choices for clarity."""
        self.fields["transaction_type"].choices = [
            (
                Transaction.TransactionType.DEPOSIT.value,
                Transaction.TransactionType.DEPOSIT.label,
            ),
            (
                Transaction.TransactionType.WITHDRAWAL.value,
                Transaction.TransactionType.WITHDRAWAL.label,
            ),
        ]


class PurchaseAgreementForm(forms.ModelForm):
    class Meta:
        model = PurchaseAgreement
        fields = ["account", "date"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        target_pk = None
        if self.instance._state.adding:
            initial_account = self.initial.get("account")
            if initial_account:
                target_pk = initial_account.pk
            elif self.is_bound and self.data.get("account"):
                target_pk = self.data.get("account")
        else:
            target_pk = self.instance.account.pk

        if target_pk:
            self.fields["account"].queryset = DepositAccount.objects.filter(
                pk=target_pk
            )
            self.fields["account"].empty_label = None


class PurchaseAgreementLineItemForm(forms.ModelForm):

    class Meta:
        model = PurchaseAgreementLineItem
        fields = ("product", "quantity_ordered", "price_per_unit")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].empty_label = "Select a product"
        self.fields["product"].queryset = Product.objects.filter(
            type_variant=Product.TypeVariant.BOXED
        ).select_related("brand")
        self.fields["product"].label_from_instance = lambda obj: (
            f"{obj.brand.name.title()} {obj.modelname.title()}"
        )


class BasePurchaseAgreementLineItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.available_balance = kwargs.pop("available_balance", None)
        super().__init__(*args, **kwargs)
        if self.instance and not self.instance._state.adding:
            self.extra = 0

    def clean(self):
        super().clean()

        if any(self.errors):
            return
        products = set()
        new_total_cost = Decimal(0)
        old_cost = Decimal(0)

        old_pks = [
            item.instance.pk
            for item in self.forms
            if getattr(item.instance, "pk", None)
        ]

        if old_pks:
            old_cost = PurchaseAgreementLineItem.objects.filter(
                pk__in=old_pks
            ).aggregate(total=Sum(F("quantity_ordered") * F("price_per_unit")))[
                "total"
            ] or Decimal(
                0
            )

        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue

            # Check for duplicate product in the form
            product = form.cleaned_data.get("product")
            if product in products:
                raise ValidationError(
                    f"Duplicate item found '{product.modelname.upper()}'. Items must be distinct."
                )
            if product is not None:
                products.add(product)

            # Check if the customer has enough balance to be used.
            quantity_ordered = form.cleaned_data.get("quantity_ordered", None)
            price_per_unit = form.cleaned_data.get("price_per_unit", None)
            line_cost = quantity_ordered * price_per_unit
            new_total_cost += line_cost

        if self.available_balance is None:
            return

        balance_to_check = self.available_balance
        if old_cost > 0:
            balance_to_check += old_cost

        if new_total_cost > balance_to_check:
            raise ValidationError(
                f"Customer has insufficient allocation balance. Available: {self.available_balance:,.2f}, "
                f"New Total Cost: {new_total_cost:,.2f}. Balance needed: {new_total_cost - old_cost:,.2f}."
            )


PurchaseAgreementLineItemFormSet = inlineformset_factory(
    parent_model=PurchaseAgreement,
    model=PurchaseAgreementLineItem,
    form=PurchaseAgreementLineItemForm,
    formset=BasePurchaseAgreementLineItemFormSet,
    can_delete=True,
    extra=1,
)


class CfaAgreementForm(forms.ModelForm):
    class Meta:
        model = CfaAgreement
        fields = ["account", "amount_allocated", "exchange_rate"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        target_pk = None
        if self.instance._state.adding:
            initial_account = self.initial.get("account")
            target_pk = initial_account.pk if initial_account else None
        else:
            target_pk = self.instance.account.pk

        if target_pk:
            self.fields["account"].queryset = DepositAccount.objects.filter(
                pk=target_pk
            )
            self.fields["account"].empty_label = None

        else:
            self.fields["account"].empty_label = "Select an account"


class CfaFulfillmentForm(forms.ModelForm):

    class Meta:
        model = CfaFulfillment
        fields = ["cfa_agreement", "date", "cfa_amount_disbursed", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }



class NormalSaleForm(forms.ModelForm):
    """Sale header form for the normal (direct) sale flow."""

    class Meta:
        model = Sale
        fields = ["customer", "payment_method"]
        widgets = {
            "customer": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude "from deposit" — that is the agreement-fulfilment flow only
        self.fields["payment_method"].choices = [
            c
            for c in Sale.PaymentMethod.choices
            if c[0] != Sale.PaymentMethod.FROM_DEPOSIT
        ]
        self.fields["customer"].queryset = (
            Customer.objects.all()
            .select_related("deposit_account")
            .order_by("full_name")
        )
        self.fields["customer"].empty_label = "Select a customer"
        self.fields["customer"].required = True


class BoxedSaleForm(forms.ModelForm):
    """Individual boxed line-item for the normal sale flow."""

    class Meta:
        model = BoxedSale
        fields = ["product", "quantity", "price"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = (
            Product.objects.filter(
                type_variant=Product.TypeVariant.BOXED,
                inventory__quantity__gt=0,
            )
            .select_related("brand")
            .order_by("modelname")
        )
        self.fields["product"].empty_label = "Select a product"
        self.fields["product"].label_from_instance = lambda obj: (
            f"{obj.brand.name.title()} {obj.modelname.title()} "
            f"(Stock: {obj.inventory.quantity})"
        )
        self.fields["quantity"].min_value = 1
        self.fields["quantity"].widget.attrs["min"] = 1
        self.fields["price"].min_value = Decimal("0.01")

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get("product")
        quantity = cleaned_data.get("quantity")

        if product and quantity:
            try:
                inventory = product.inventory
            except Inventory.DoesNotExist:
                raise forms.ValidationError(
                    {"product": f"No inventory record exists for {product.modelname}."}
                )
            if quantity > inventory.quantity:
                raise forms.ValidationError(
                    {
                        "quantity": (
                            f"Insufficient stock. Available: {inventory.quantity}, "
                            f"Requested: {quantity}"
                        )
                    }
                )
        return cleaned_data


class BaseBoxedSaleFormSet(BaseInlineFormSet):
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
                raise forms.ValidationError(
                    f"Duplicate product '{product.modelname.upper()}'. "
                    "Each product can only appear once."
                )
            if product:
                products.add(product)


BoxedSaleFormSet = inlineformset_factory(
    Sale,
    BoxedSale,
    form=BoxedSaleForm,
    formset=BaseBoxedSaleFormSet,
    extra=1,
    can_delete=True,
)


class CoupledSaleForm(forms.ModelForm):
    """Individual serialized / coupled line-item for the normal sale flow."""

    class Meta:
        model = CoupledSale
        fields = ["transformation_item", "price"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["transformation_item"].queryset = (
            TransformationItem.objects.filter(
                status=TransformationItem.Status.AVAILABLE,
            )
            .select_related("target_product__brand")
            .order_by("target_product__modelname")
        )
        self.fields["transformation_item"].empty_label = "Select a serial item"
        self.fields["transformation_item"].label_from_instance = lambda obj: (
            f"{obj.target_product.brand.name.title()} {obj.target_product.modelname.title()} — "
            f"ENG: ...{obj.engine_number[-5:]} | CHA: ...{obj.chassis_number[-5:]}"
        )
        self.fields["price"].min_value = Decimal("0.01")

    def clean(self):
        cleaned_data = super().clean()
        transformation_item = cleaned_data.get("transformation_item")
        if transformation_item and transformation_item.status != TransformationItem.Status.AVAILABLE:
            raise forms.ValidationError(
                {
                    "transformation_item": (
                        f"This item is not available for sale "
                        f"(status: {transformation_item.get_status_display()})."
                    )
                }
            )
        return cleaned_data


class BaseCoupledSaleFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        items = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            ti = form.cleaned_data.get("transformation_item")
            if ti in items:
                raise forms.ValidationError(
                    "Duplicate serial item selected. Each item can only be sold once."
                )
            if ti:
                items.add(ti)


CoupledSaleFormSet = inlineformset_factory(
    Sale,
    CoupledSale,
    form=CoupledSaleForm,
    formset=BaseCoupledSaleFormSet,
    extra=1,
    can_delete=True,
)


# ─── Agreement Amendment ───

class AmendLineItemForm(forms.Form):
    """Form for amending an existing PurchaseAgreementLineItem."""

    new_quantity = forms.IntegerField(min_value=1)
    new_price_per_unit = forms.DecimalField(
        max_digits=15, decimal_places=2, min_value=Decimal("0.01")
    )
    reason = forms.CharField(max_length=255, required=False, widget=forms.TextInput)

    def __init__(self, *args, line_item=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.line_item = line_item
        if line_item:
            fulfilled = line_item.quantity_fulfilled_accross_all_versions
            self.fields["new_quantity"].min_value = fulfilled
            self.fields["new_quantity"].widget.attrs["min"] = fulfilled

    def clean_new_quantity(self):
        quantity = self.cleaned_data["new_quantity"]
        if self.line_item and quantity < self.line_item.quantity_fulfilled_accross_all_versions:
            raise forms.ValidationError(
                f"Cannot set quantity below {self.line_item.quantity_fulfilled_accross_all_versions} "
                f"— {self.line_item.quantity_fulfilled_accross_all_versions} units have already been fulfilled."
            )
        return quantity


# ─── Agreement Fulfillment Flow ───

class AgreementFulfillmentLineForm(forms.Form):
    """One row per PurchaseAgreementLineItem during fulfilment.

    Each line can be fulfilled as:
      • Boxed — enter a quantity
      • Coupled — pick one or more TransformationItems (multi-select)
      • Mixed — both boxed qty AND coupled units in the same row
    """

    line_item = forms.UUIDField(widget=forms.HiddenInput)
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(type_variant=Product.TypeVariant.BOXED),
        widget=forms.HiddenInput,
        required=True,
    )
    price = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal("0.01"),
        widget=forms.HiddenInput,
    )
    quantity = forms.IntegerField(min_value=0, initial=0, required=False)
    transformation_items = forms.ModelMultipleChoiceField(
        queryset=TransformationItem.objects.none(),
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                "class": "select2-multi-serial",
                "data-placeholder": "Select serialized units…",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product_pk = self.initial.get("product")

        # Bound form (POST with errors) — extract product from submitted data
        if not product_pk and self.is_bound:
            product_pk = self.data.get(self.add_prefix("product"))

        # Fallback: derive product from the agreement line item
        if not product_pk:
            line_item_pk = self.initial.get("line_item")
            if not line_item_pk and self.is_bound:
                line_item_pk = self.data.get(self.add_prefix("line_item"))
            if line_item_pk:
                try:
                    line = PurchaseAgreementLineItem.objects.get(pk=line_item_pk)
                    product_pk = line.product.pk
                except PurchaseAgreementLineItem.DoesNotExist:
                    pass

        if product_pk:
            # Lock the product queryset so the template only shows the
            # agreement line’s product.
            self.fields["product"].queryset = Product.objects.filter(pk=product_pk)
            self.fields["product"].initial = product_pk

            # Build transformation-item queryset:
            # Show available items for this boxed product.  On bound forms
            # also include currently selected items so re-renders keep them.
            ti_qs = TransformationItem.objects.filter(source_product_id=product_pk)
            if self.is_bound:
                selected = self.data.getlist(self.add_prefix("transformation_items"))
                if selected:
                    ti_qs = ti_qs.filter(
                        Q(status=TransformationItem.Status.AVAILABLE)
                        | Q(pk__in=selected)
                    )
                else:
                    ti_qs = ti_qs.filter(status=TransformationItem.Status.AVAILABLE)
            else:
                ti_qs = ti_qs.filter(status=TransformationItem.Status.AVAILABLE)
            self.fields["transformation_items"].queryset = ti_qs.order_by(
                "item_number"
            )

    def clean(self):
        cleaned_data = super().clean()
        quantity = cleaned_data.get("quantity") or 0
        transformation_items = cleaned_data.get("transformation_items") or []
        line_item_id = cleaned_data.get("line_item")

        total = quantity + len(transformation_items)

        if total > 0 and line_item_id:
            try:
                line = PurchaseAgreementLineItem.objects.get(pk=line_item_id)
            except PurchaseAgreementLineItem.DoesNotExist:
                raise forms.ValidationError("Invalid agreement line item.")

            if total > line.remaining_quantity:
                raise forms.ValidationError(
                    f"Cannot fulfil more than the remaining quantity. "
                    f"Remaining: {line.remaining_quantity}, Requested: {total} "
                    f"({quantity} boxed + {len(transformation_items)} coupled)"
                )

            # Stock check for boxed quantity
            if quantity > 0:
                try:
                    inventory = line.product.inventory
                except Inventory.DoesNotExist:
                    raise forms.ValidationError(
                        f"No inventory record exists for {line.product.modelname}."
                    )
                if quantity > inventory.quantity:
                    raise forms.ValidationError(
                        f"Insufficient stock. Available: {inventory.quantity}, "
                        f"Requested: {quantity}"
                    )

            # Validate each selected transformation item
            for ti in transformation_items:
                if ti.source_product_id != line.product_id:
                    raise forms.ValidationError(
                        f"Selected item {ti.item_number} does not match the agreement product."
                    )
                if ti.status != TransformationItem.Status.AVAILABLE:
                    raise forms.ValidationError(
                        f"Selected item {ti.item_number} is not available "
                        f"(status: {ti.get_status_display()})."
                    )

        return cleaned_data


class BaseAgreementFulfillmentFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        total = 0
        for form in self.forms:
            qty = form.cleaned_data.get("quantity") or 0
            coupled = len(form.cleaned_data.get("transformation_items") or [])
            total += qty + coupled
        if total == 0:
            raise forms.ValidationError("You must fulfil at least one item.")


AgreementFulfillmentFormSet = forms.formset_factory(
    AgreementFulfillmentLineForm,
    formset=BaseAgreementFulfillmentFormSet,
    extra=0,
)
