from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum
from .models import (
    Customer,
    DepositAccount,
    Transaction,
    PurchaseAgreement,
    PurchaseAgreementLineItem,
    Sale,
    CoupledSale,
    BoxedSale,
    CfaAgreement,
    CfaFulfillment,
)


class AuditLogAdminMixin:
    """
    Mixin to handle created_by and updated_by fields automatically
    and make audit fields read-only.
    """

    readonly_fields = [
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if not obj.pk:
                if hasattr(obj, "created_by"):
                    obj.created_by = request.user
            if hasattr(obj, "updated_by"):
                obj.updated_by = request.user
            obj.save()
        formset.save_m2m()


class PurchaseAgreementLineItemInline(admin.TabularInline):
    model = PurchaseAgreementLineItem
    extra = 0
    readonly_fields = [
        "line_number",
        "quantity_fulfilled_display",
        "remaining_quantity_display",
        "created_by",
        "updated_by",
        "created_at",
    ]
    fields = [
        "product",
        "line_number",
        "quantity_ordered",
        "price_per_unit",
        "status",
        "version",
        "is_current_version",
        "quantity_fulfilled_display",
        "remaining_quantity_display",
    ]
    show_change_link = True

    def quantity_fulfilled_display(self, obj):
        return obj.quantity_fulfilled_accross_all_versions

    quantity_fulfilled_display.short_description = "Fulfilled Qty"

    def remaining_quantity_display(self, obj):
        return obj.remaining_quantity

    remaining_quantity_display.short_description = "Remaining Qty"


class BoxedSaleInline(admin.StackedInline):
    model = BoxedSale
    extra = 0
    readonly_fields = [
        "boxed_sale_number",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
    autocomplete_fields = ["product", "agreement_line_item"]


class CoupledSaleInline(admin.StackedInline):
    model = CoupledSale
    extra = 0
    readonly_fields = [
        "coupled_sale_number",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    ]
    autocomplete_fields = ["transformation_item", "agreement_line_item"]


class CfaFulfillmentInline(admin.TabularInline):
    model = CfaFulfillment
    extra = 0
    readonly_fields = ["fulfillment_number", "created_at", "created_by"]
    fields = [
        "date",
        "cfa_amount_disbursed",
        "fulfillment_number",
        "notes",
    ]
    show_change_link = True


class TransactionInline(admin.TabularInline):
    model = Transaction
    extra = 0
    fields = ["transaction_type", "amount", "status", "reference_number", "created_at"]
    readonly_fields = ["reference_number", "created_at"]
    ordering = ["-created_at"]
    show_change_link = True

    def has_add_permission(self, request, obj):
        return False


@admin.register(Customer)
class CustomerAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "customer_number",
        "full_name",
        "phone",
        "deposit_account_link",
        "created_at",
    ]
    search_fields = ["customer_number", "full_name", "phone", "email"]
    list_filter = ["created_at"]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "customer_id",
        "customer_number",
    ]

    def deposit_account_link(self, obj):
        if hasattr(obj, "deposit_account"):
            url = reverse(
                "admin:customer_depositaccount_change", args=[obj.deposit_account.pk]
            )
            return format_html(
                '<a href="{}">{}</a>', url, obj.deposit_account.account_number
            )
        return "-"

    deposit_account_link.short_description = "Deposit Account"


@admin.register(DepositAccount)
class DepositAccountAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "account_number",
        "customer",
        "display_total_balance",
        "display_allocated_balance",
        "display_available_balance",
    ]
    search_fields = [
        "account_number",
        "customer__full_name",
        "customer__customer_number",
    ]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "account_id",
        "account_number",
        "display_total_balance",
        "display_allocated_balance",
        "display_available_balance",
    ]
    inlines = [TransactionInline]

    def customer_link(self, obj):
        url = reverse("admin:customer_customer_change", args=[obj.customer.pk])
        return format_html('<a href="{}">{}</a>', url, obj.customer.full_name)

    customer_link.short_description = "Customer"

    def display_total_balance(self, obj):
        return f"{obj.total_balance:,.2f}"

    display_total_balance.short_description = "Total Balance"

    def display_allocated_balance(self, obj):
        return f"{obj.allocated_balance:,.2f}"

    display_allocated_balance.short_description = "Allocated"

    def display_available_balance(self, obj):
        return f"{obj.available_balance:,.2f}"

    display_available_balance.short_description = "Available"


@admin.register(Transaction)
class TransactionAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "reference_number",
        "account",
        "transaction_type",
        "amount",
        "status",
        "created_at",
    ]
    list_filter = ["transaction_type", "status", "created_at"]
    search_fields = [
        "reference_number",
        "account__account_number",
        "account__customer__full_name",
    ]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "transaction_id",
        "reference_number",
        "source_content_type",
        "source_object_id",
        "source",
    ]
    autocomplete_fields = ["account"]

    def account_link(self, obj):
        url = reverse("admin:customer_depositaccount_change", args=[obj.account.pk])
        return format_html('<a href="{}">{}</a>', url, obj.account.account_number)

    account_link.short_description = "Account"


@admin.register(PurchaseAgreement)
class PurchaseAgreementAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "purchase_agreement_number",
        "account",
        "status",
        "date",
        "total_allocated_amount_display",
        "fulfillment_progress",
    ]
    list_filter = ["status", "date"]
    search_fields = [
        "purchase_agreement_number",
        "account__account_number",
        "account__customer__full_name",
    ]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "purchase_agreement_id",
        "purchase_agreement_number",
        "total_allocated_amount_display",
    ]
    inlines = [PurchaseAgreementLineItemInline]
    autocomplete_fields = ["account"]

    def account_link(self, obj):
        url = reverse("admin:customer_depositaccount_change", args=[obj.account.pk])
        return format_html('<a href="{}">{}</a>', url, obj.account.customer.full_name)

    account_link.short_description = "Customer Account"

    def total_allocated_amount_display(self, obj):
        return f"{obj.total_allocated_amount:,.2f}"

    total_allocated_amount_display.short_description = "Total Allocated"

    def fulfillment_progress(self, obj):
        ordered = obj.total_quantity_ordered
        fulfilled = obj.total_quantity_fulfilled
        return f"{fulfilled:,.0f} / {ordered:,.0f}"

    fulfillment_progress.short_description = "Fulfilled / Ordered"


@admin.register(PurchaseAgreementLineItem)
class PurchaseAgreementLineItemAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "line_number",
        "purchase_agreement",
        "product",
        "quantity_ordered",
        "status",
        "is_current_version",
    ]
    list_filter = ["status", "is_current_version", "product"]
    search_fields = ["line_number", "purchase_agreement__purchase_agreement_number"]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "line_item_id",
        "line_number",
    ]
    autocomplete_fields = ["product", "purchase_agreement", "superseded_by"]


@admin.register(Sale)
class SaleAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "sale_date",
        "sale_number",
        "customer",
        "payment_method",
        "status",
    ]
    list_filter = ["payment_method", "status", "sale_date"]
    search_fields = [
        "sale_number",
        "customer__full_name",
        "agreement__purchase_agreement_number",
    ]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "sale_id",
        "sale_number",
        "status",
    ]
    inlines = [BoxedSaleInline, CoupledSaleInline]
    autocomplete_fields = ["customer", "agreement"]


@admin.register(CfaAgreement)
class CfaAgreementAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "cfa_agreement_number",
        "account",
        "amount_allocated",
        "exchange_rate",
        "status",
        "remaining_cfa_display",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["cfa_agreement_number", "account__account_number"]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "cfa_agreement_id",
        "cfa_agreement_number",
        "expected_cfa_amount_display",
    ]
    inlines = [CfaFulfillmentInline]
    autocomplete_fields = ["account"]

    def remaining_cfa_display(self, obj):
        return f"{obj.remaining_cfa:,.2f}"

    remaining_cfa_display.short_description = "Remaining CFA"

    def expected_cfa_amount_display(self, obj):
        return f"{obj.expected_cfa_amount:,.2f}"

    expected_cfa_amount_display.short_description = "Expected Total CFA"


@admin.register(CfaFulfillment)
class CfaFulfillmentAdmin(AuditLogAdminMixin, admin.ModelAdmin):
    list_display = [
        "fulfillment_number",
        "cfa_agreement",
        "date",
        "cfa_amount_disbursed",
    ]
    search_fields = ["fulfillment_number", "cfa_agreement__cfa_agreement_number"]
    list_filter = ["date"]
    readonly_fields = AuditLogAdminMixin.readonly_fields + [
        "fulfillment_id",
        "fulfillment_number",
        "cfa_amount_disbursed_to_naira_display",
    ]
    autocomplete_fields = ["cfa_agreement"]

    def cfa_amount_disbursed_to_naira_display(self, obj):
        return f"{obj.cfa_amount_disbursed_to_naira:,.2f}"

    cfa_amount_disbursed_to_naira_display.short_description = "Implied Naira Value"
