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
from inventory.models import Product, TransformationItem
from django.forms import modelformset_factory, BaseModelFormSet
from django.db.models import Sum, F
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


class PurchaseAgreementLineItemForm(forms.ModelForm):

    class Meta:
        model = PurchaseAgreementLineItem
        fields = ("product", "quantity_ordered", "price_per_unit")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].empty_label = "Select an Product"


class BasePurchaseAgreementLineItemFormSet(BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        self.available_balance = kwargs.pop("available_balance", None)
        super().__init__(*args, **kwargs)

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

        balance_to_check = self.available_balance
        if old_cost > 0:
            balance_to_check += old_cost

        if new_total_cost > balance_to_check:
            raise ValidationError(
                f"Customer has insufficient allocation balance. Available: {self.available_balance:,.2f}, "
                f"New Total Cost: {new_total_cost:,.2f}. Balance needed: {new_total_cost - old_cost:,.2f}."
            )


PurchaseAgreementLineItemFormSet = modelformset_factory(
    PurchaseAgreementLineItem,
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        target_pk = None
        if self.instance._state.adding:
            initial_cfa_agreement = self.initial.get("cfa_agreement")
            target_pk = initial_cfa_agreement.pk if initial_cfa_agreement else None
        else:
            target_pk = self.instance.cfa_agreement.pk

        if target_pk:
            self.fields["cfa_agreement"].queryset = CfaAgreement.objects.filter(
                pk=target_pk
            )
            self.fields["cfa_agreement"].empty_label = None

        else:
            self.fields["cfa_agreement"].empty_label = "Select an cfa_agreement"


class BaseSaleItemForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.agreement_line_item = kwargs.pop("agreement_line_item", None)
        super().__init__(*args, **kwargs)

        # If this is an agreement sale, lock specific fields
        if self.agreement_line_item:
            self.fields["agreement_line_item"].initial = self.agreement_line_item
            self.fields["agreement_line_item"].widget = forms.HiddenInput()
            self.fields["price"].initial = self.agreement_line_item.price_per_unit
            self.fields["price"].widget.attrs["readonly"] = True

            # For Boxed Sale
            if "product" in self.fields:
                self.fields["product"].initial = self.agreement_line_item.product
                self.fields["product"].widget.attrs["readonly"] = True
                self.fields["product"].disabled = True


class BoxedSaleForm(BaseSaleItemForm):
    class Meta:
        model = BoxedSale
        fields = ["product", "quantity", "price", "agreement_line_item"]


class CoupledSaleForm(BaseSaleItemForm):
    class Meta:
        model = CoupledSale
        fields = ["transformation_item", "price", "agreement_line_item"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.agreement_line_item:
            self.fields["transformation_item"].queryset = (
                TransformationItem.objects.filter(
                    product=Product.objects.get(
                        base_product=self.agreement_line_item.product
                    )
                )
            )


class NormalSaleForm(forms.ModelForm):
    # Field for non-system customers
    new_customer_name = forms.CharField(
        max_length=200,
        required=False,
        help_text="Enter full name if customer is not in the list.",
    )

    class Meta:
        model = Sale
        fields = ["customer", "payment_method", "new_customer_name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Filter out 'from deposit' payment method
        self.fields["payment_method"].choices = [
            c
            for c in Sale.PaymentMethod.choices
            if c[0] != Sale.PaymentMethod.FROM_DEPOSIT
        ]

        # 2. Make customer optional (since we might use new_customer_name)
        self.fields["customer"].required = False
        self.fields["customer"].help_text = (
            "Select existing or leave blank and fill 'New Customer Name'."
        )

    def clean(self):
        cleaned_data = super().clean()
        customer = cleaned_data.get("customer")
        new_name = cleaned_data.get("new_customer_name")

        if not customer and not new_name:
            raise forms.ValidationError(
                "You must either select a Customer or enter a New Customer Name."
            )

        return cleaned_data

    def save(self, commit=True):
        # Handle dynamic customer creation
        new_name = self.cleaned_data.get("new_customer_name")
        if not self.cleaned_data.get("customer") and new_name:
            # Create the customer on the fly
            customer = Customer.objects.create(
                full_name=new_name,
                phone="0000000000",  # Default or add phone field to form
            )
            self.instance.customer = customer

        return super().save(commit)


class AgreementSaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ["customer", "payment_method", "agreement"]

    def __init__(self, *args, **kwargs):
        self.agreement_line = kwargs.pop("agreement_line_item", None)
        super().__init__(*args, **kwargs)

        if self.agreement_line:
            agreement = self.agreement_line.purchase_agreement
            customer = agreement.account.customer

            # PREFILL and LOCK Customer
            self.fields["customer"].initial = customer
            self.fields["customer"].disabled = True

            # PREFILL and LOCK Agreement
            self.fields["agreement"].initial = agreement
            self.fields["agreement"].disabled = True

            # PREFILL and LOCK Payment Method
            self.fields["payment_method"].initial = Sale.PaymentMethod.FROM_DEPOSIT
            self.fields["payment_method"].disabled = True


# FormSets
BoxedSaleFormSet = inlineformset_factory(
    Sale, BoxedSale, form=BoxedSaleForm, extra=1, can_delete=True
)

CoupledSaleFormSet = inlineformset_factory(
    Sale, CoupledSale, form=CoupledSaleForm, extra=1, can_delete=True
)
