from core.models import AuditLog
from account.models import CustomUser
from django.core.paginator import Paginator
from django.db.models import Sum, Count, F, Q, DecimalField, Value
from django.db.models.functions import TruncMonth, TruncDay, Coalesce
from django.utils import timezone
from datetime import timedelta, datetime
from customer.models import Sale, Customer, Transaction, BoxedSale, CoupledSale, DepositAccount, PurchaseAgreement, CfaAgreement
from inventory.models import Product, Inventory
from supply_chain.models import PurchaseOrder, Payment, GoodsReceipt
import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django_htmx.http import replace_url, HttpResponseClientRedirect
from django_htmx.middleware import HtmxDetails
from django.http import HttpResponse
from django.contrib import messages
from render_block import render_block_to_string
from django.template.loader import render_to_string

def dashboard(request):
    today = timezone.now().date()
    current_month = timezone.now().month
    current_year = timezone.now().year

    # --- Date range filtering ---
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')
    period = request.GET.get('period', 'month')  # kept for backward compat

    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            period_label = f"{start_date_str} – {end_date_str}"
            use_range = True
        except (ValueError, TypeError):
            use_range = False
    else:
        use_range = False

    if not use_range:
        if period == 'last_month':
            last_month_date = today.replace(day=1) - timedelta(days=1)
            start_date = last_month_date.replace(day=1)
            end_date = last_month_date
            period_label = last_month_date.strftime('%B %Y')
        elif period == 'year':
            start_date = today.replace(month=1, day=1)
            end_date = today.replace(month=12, day=31)
            period_label = str(current_year)
        else:
            start_date = today.replace(day=1)
            end_date = today
            period_label = today.strftime('%B %Y')

    def period_filter(queryset, date_field):
        return queryset.filter(**{f'{date_field}__date__gte': start_date, f'{date_field}__date__lte': end_date})

    # --- Safe revenue calculation helpers ---
    # Use separate aggregates on BoxedSale + CoupledSale to avoid NULL poisoning
    # and cartesian-product bugs from joining two reverse relations in one Sum expr.
    def _revenue_in_range(start, end):
        """Total revenue from ACTIVE sales with sale_date in [start, end] (inclusive)."""
        boxed = BoxedSale.objects.filter(
            sale__status=Sale.Status.ACTIVE,
            sale__sale_date__date__gte=start,
            sale__sale_date__date__lte=end,
        ).aggregate(
            total=Coalesce(
                Sum(F("price") * F("quantity"), output_field=DecimalField()),
                Value(Decimal("0.00")),
                output_field=DecimalField(),
            )
        )["total"] or Decimal("0.00")

        coupled = CoupledSale.objects.filter(
            sale__status=Sale.Status.ACTIVE,
            sale__sale_date__date__gte=start,
            sale__sale_date__date__lte=end,
        ).aggregate(
            total=Coalesce(
                Sum("price", output_field=DecimalField()),
                Value(Decimal("0.00")),
                output_field=DecimalField(),
            )
        )["total"] or Decimal("0.00")

        return boxed + coupled

    # --- Financial Metrics ---
    daily_sales = _revenue_in_range(today, today)

    period_sales = _revenue_in_range(start_date, end_date)

    year_start = today.replace(month=1, day=1)
    year_end = today.replace(month=12, day=31)
    yearly_sales = _revenue_in_range(year_start, year_end)

    # Supplier payments (inventory purchases — not expenses, shown separately)
    supplier_payments = period_filter(
        Payment.objects.filter(status=Payment.Status.PAID), 'payment_date'
    ).aggregate(total=Sum('amount_paid'))['total'] or 0

    # --- Gross Profit ---
    boxed_cost_qs = BoxedSale.objects.filter(sale__status=Sale.Status.ACTIVE)
    coupled_cost_qs = CoupledSale.objects.filter(sale__status=Sale.Status.ACTIVE)
    boxed_cost_qs = period_filter(boxed_cost_qs, 'sale__sale_date')
    coupled_cost_qs = period_filter(coupled_cost_qs, 'sale__sale_date')

    boxed_cost = boxed_cost_qs.aggregate(
        total=Coalesce(
            Sum(
                Coalesce(
                    "cost_basis",
                    F("quantity") * F("product__inventory__weighted_average_cost"),
                    output_field=DecimalField(),
                ),
                output_field=DecimalField(),
            ),
            Value(Decimal("0.00")),
            output_field=DecimalField(),
        )
    )["total"] or Decimal("0.00")

    coupled_cost = coupled_cost_qs.aggregate(
        total=Coalesce(
            Sum("transformation_item__unit_cost_at_transformation", output_field=DecimalField()),
            Value(Decimal("0.00")),
            output_field=DecimalField(),
        )
    )["total"] or Decimal("0.00")

    cost_of_goods = boxed_cost + coupled_cost

    period_gross_profit = period_sales - cost_of_goods
    period_net_profit = period_gross_profit
    period_profit_margin = (period_gross_profit / period_sales * 100) if period_sales > 0 else 0

    # --- Customer Balances ---
    balance_agg = DepositAccount.objects.aggregate(
        total=Coalesce(Sum('cached_total_balance'), Decimal('0.00')),
        allocated=Coalesce(Sum('cached_allocated_balance'), Decimal('0.00')),
        available=Coalesce(Sum('cached_available_balance'), Decimal('0.00')),
    )
    total_customer_balances = balance_agg['total']
    total_allocated_balances = balance_agg['allocated']
    total_available_balances = balance_agg['available']

    active_agreement_count = PurchaseAgreement.objects.filter(
        status=PurchaseAgreement.Status.ACTIVE
    ).count()

    # --- Charts Data ---
    last_7_days = today - timedelta(days=6)
    days_labels = []
    days_data = []
    for i in range(7):
        day = last_7_days + timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        days_labels.append(day_str)
        rev = _revenue_in_range(day, day)
        days_data.append(float(rev))

    chart_max = max(days_data) if days_data else 1
    if chart_max == 0:
        chart_max = 1

    svg_bars = []
    for i, (day_label, value) in enumerate(zip(days_labels, days_data)):
        day_date = datetime.strptime(day_label, '%Y-%m-%d')
        day_name = day_date.strftime('%a')
        x = 10 + i * 58
        height = (value / chart_max) * 105
        y = 120 - height
        is_highlight = value >= chart_max * 0.7
        svg_bars.append({
            'x': x,
            'y': y,
            'height': height,
            'fill': '#d97706' if is_highlight else '#fbbf24',
            'opacity': '0.85' if is_highlight else '0.55',
            'day_name': day_name,
            'value': value,
        })

    # --- Top Selling Products ---
    # Compute using separate per-channel aggregates + python merge to avoid
    # cross-relation Sum cartesian / date-filter join duplication bugs.
    boxed_revenue = (
        BoxedSale.objects.filter(
            sale__status=Sale.Status.ACTIVE,
            sale__sale_date__date__gte=start_date,
            sale__sale_date__date__lte=end_date,
        )
        .values("product_id")
        .annotate(
            rev=Coalesce(
                Sum(F("price") * F("quantity"), output_field=DecimalField()),
                Value(Decimal("0.00")),
            )
        )
    )
    boxed_map = {item["product_id"]: item["rev"] for item in boxed_revenue}

    coupled_revenue = (
        CoupledSale.objects.filter(
            sale__status=Sale.Status.ACTIVE,
            sale__sale_date__date__gte=start_date,
            sale__sale_date__date__lte=end_date,
        )
        .values("transformation_item__target_product_id")
        .annotate(
            rev=Coalesce(Sum("price", output_field=DecimalField()), Value(Decimal("0.00")))
        )
    )
    coupled_map = {
        item["transformation_item__target_product_id"]: item["rev"] for item in coupled_revenue
    }

    all_revenues = {}
    for pid, rev in boxed_map.items():
        all_revenues[pid] = all_revenues.get(pid, Decimal("0.00")) + rev
    for pid, rev in coupled_map.items():
        all_revenues[pid] = all_revenues.get(pid, Decimal("0.00")) + rev

    sorted_items = sorted(all_revenues.items(), key=lambda x: x[1], reverse=True)[:5]
    top_pids = [pid for pid, _ in sorted_items]
    top_products = list(Product.objects.filter(pk__in=top_pids)) if top_pids else []

    rev_map = {pid: rev for pid, rev in sorted_items}
    for p in top_products:
        p.total_revenue = rev_map.get(p.pk, Decimal("0.00"))
    top_products.sort(key=lambda p: p.total_revenue, reverse=True)

    max_revenue = max([float(p.total_revenue) for p in top_products], default=1) or 1
    for p in top_products:
        p.revenue_percent = int((float(p.total_revenue) / max_revenue) * 100)

    # --- Sales by Category ---
    category_qs = BoxedSale.objects.filter(sale__status=Sale.Status.ACTIVE)
    category_qs = period_filter(category_qs, 'sale__sale_date')

    sales_by_category = category_qs.values('product__category').annotate(
        total=Sum(F('price') * F('quantity'))
    ).order_by('-total')

    category_labels = [item['product__category'].title() for item in sales_by_category]
    category_data = [float(item['total']) for item in sales_by_category]

    # --- Recent Activity ---
    # Avoid fragile annotate; reuse the model's sales_total property which
    # safely aggregates boxed + coupled separately.
    recent_sales = (
        Sale.objects.filter(status=Sale.Status.ACTIVE)
        .select_related("customer")
        .order_by("-sale_date")[:5]
    )
    for sale in recent_sales:
        sale.calc_total = sale.sales_total

    recent_deposits = Transaction.objects.filter(
        status=Transaction.Status.ACTIVE,
        transaction_type=Transaction.TransactionType.DEPOSIT,
    ).select_related('account', 'account__customer').order_by('-created_at')[:5]

    # --- Attention Alerts ---
    LOW_STOCK_THRESHOLD = 5
    low_stock = Inventory.objects.filter(
        quantity__lte=LOW_STOCK_THRESHOLD, quantity__gt=0
    ).select_related('product', 'product__brand').order_by('quantity')[:5]

    stockout = Inventory.objects.filter(
        quantity=0
    ).select_related('product', 'product__brand')[:5]

    pending_deliveries_qs = PurchaseOrder.objects.filter(
        delivery_status__in=[
            PurchaseOrder.DeliveryStatus.PENDING,
            PurchaseOrder.DeliveryStatus.PARTIALLY_RECEIVED,
        ]
    ).select_related('supplier').order_by('-created_at')[:3]

    idle_balances = DepositAccount.objects.filter(
        cached_available_balance__gte=500000
    ).select_related('customer').order_by('-cached_available_balance')[:3]

    # --- Inventory Metrics ---
    total_stock_value = Inventory.objects.aggregate(
        total=Sum(F('quantity') * F('weighted_average_cost'))
    )['total'] or 0

    # --- Customer Metrics ---
    total_customers = Customer.objects.count()
    new_customers_period = period_filter(
        Customer.objects.all(), 'created_at'
    ).count()

    # --- Supply Chain ---
    pending_deliveries_count = PurchaseOrder.objects.filter(
        delivery_status__in=[
            PurchaseOrder.DeliveryStatus.PENDING,
            PurchaseOrder.DeliveryStatus.PARTIALLY_RECEIVED,
        ]
    ).count()

    show_attention = bool(low_stock or stockout or pending_deliveries_qs or idle_balances)
    attention_count = len(low_stock) + len(stockout) + len(pending_deliveries_qs) + len(idle_balances)

    hour = timezone.now().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    context = {
        'start_date': start_date_str or start_date.strftime('%Y-%m-%d'),
        'end_date': end_date_str or end_date.strftime('%Y-%m-%d'),
        'period_label': period_label,
        'daily_sales': daily_sales,
        'period_sales': period_sales,
        'yearly_sales': yearly_sales,
        'period_expenses': supplier_payments,
        'period_gross_profit': period_gross_profit,
        'period_net_profit': period_net_profit,
        'period_profit_margin': period_profit_margin,
        'total_customer_balances': total_customer_balances,
        'total_allocated_balances': total_allocated_balances,
        'total_available_balances': total_available_balances,
        'active_agreement_count': active_agreement_count,
        'recent_sales': recent_sales,
        'recent_deposits': recent_deposits,
        'total_stock_value': total_stock_value,
        'total_customers': total_customers,
        'new_customers_period': new_customers_period,
        'days_labels': json.dumps(days_labels),
        'days_data': json.dumps(days_data),
        'top_products_names': json.dumps([p.modelname for p in top_products]),
        'top_products_data': json.dumps([float(p.total_revenue) for p in top_products]),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
        'period': period,
        'period_label': period_label,
        'low_stock': low_stock,
        'stockout': stockout,
        'pending_deliveries': pending_deliveries_qs,
        'idle_balances': idle_balances,
        'show_attention': show_attention,
        'attention_count': attention_count,
        'svg_bars': svg_bars,
        'top_products': top_products,
        'greeting': greeting,
    }

    if request.htmx:
        return render(request, "dashboard.html#dashboard-metrics-partial", context)

    return render(request, "dashboard.html", context)


def audit_log(request):
    search_query = request.GET.get("q", "")
    action_filter = request.GET.get("action", "")
    user_filter = request.GET.get("user", "")
    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    sort_by = request.GET.get("sort", "newest")

    logs = AuditLog.objects.select_related("user").all()

    if search_query:
        logs = logs.filter(
            Q(action__icontains=search_query)
            | Q(object_repr__icontains=search_query)
            | Q(object_type__icontains=search_query)
        )

    if action_filter:
        logs = logs.filter(action=action_filter)

    if user_filter:
        logs = logs.filter(user_id=user_filter)

    if start_date:
        logs = logs.filter(timestamp__date__gte=start_date)

    if end_date:
        logs = logs.filter(timestamp__date__lte=end_date)

    if sort_by == "oldest":
        logs = logs.order_by("timestamp")
    else:
        logs = logs.order_by("-timestamp")

    PAGE_SIZE = 50
    paginator = Paginator(logs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    distinct_actions = (
        AuditLog.objects.values_list("action", flat=True)
        .distinct()
        .order_by("action")
    )
    distinct_users = CustomUser.objects.filter(
        auditlog__isnull=False
    ).distinct().order_by("first_name", "last_name")

    params = {}
    if search_query:
        params["q"] = search_query
    if action_filter:
        params["action"] = action_filter
    if user_filter:
        params["user"] = user_filter
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if sort_by != "newest":
        params["sort"] = sort_by

    context = {
        "logs": page_obj,
        "search_query": search_query,
        "action_filter": action_filter,
        "user_filter": user_filter,
        "start_date": start_date,
        "end_date": end_date,
        "sort_by": sort_by,
        "distinct_actions": distinct_actions,
        "distinct_users": distinct_users,
        "params": params,
    }

    if request.htmx:
        if any(
            key in request.GET
            for key in ["page", "q", "action", "user", "start_date", "end_date", "sort"]
        ):
            return render(
                request,
                "core/audit_log.html#auditlog-table-partial",
                context,
            )
        return render(
            request,
            "core/audit_log.html#auditlog-list-partial",
            context,
        )

    return render(request, "core/audit_log.html", context)
