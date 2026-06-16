from core.models import AuditLog
from account.models import CustomUser
from django.core.paginator import Paginator
from django.db.models import Sum, Count, F, Q, DecimalField, Value
from django.db.models.functions import TruncMonth, TruncDay, Coalesce
from django.utils import timezone
from datetime import timedelta, datetime
from customer.models import Sale, Customer, Transaction, BoxedSale, CoupledSale, DepositAccount
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
    
    # --- Period filtering ---
    period = request.GET.get('period', 'month')
    if period == 'last_month':
        last_month_date = today.replace(day=1) - timedelta(days=1)
        filter_month = last_month_date.month
        filter_year = last_month_date.year
        period_label = last_month_date.strftime('%B %Y')
    elif period == 'year':
        filter_month = None
        filter_year = current_year
        period_label = str(current_year)
    else:  # month (default)
        filter_month = current_month
        filter_year = current_year
        period_label = today.strftime('%B %Y')
    
    # --- Date filters helper ---
    def sale_date_filter(queryset, date_field='sale_date'):
        if filter_month:
            return queryset.filter(**{
                f'{date_field}__month': filter_month,
                f'{date_field}__year': filter_year,
            })
        return queryset.filter(**{f'{date_field}__year': filter_year})
    
    def payment_date_filter(queryset):
        if filter_month:
            return queryset.filter(
                payment_date__month=filter_month,
                payment_date__year=filter_year,
            )
        return queryset.filter(payment_date__year=filter_year)
    
    # --- Financial Metrics ---
    daily_sales = Sale.objects.filter(
        sale_date__date=today, status=Sale.Status.ACTIVE
    ).aggregate(
        total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price')
    )['total'] or 0
    
    period_sales = sale_date_filter(
        Sale.objects.filter(status=Sale.Status.ACTIVE)
    ).aggregate(
        total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price')
    )['total'] or 0
    
    yearly_sales = Sale.objects.filter(
        sale_date__year=current_year, status=Sale.Status.ACTIVE
    ).aggregate(
        total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price')
    )['total'] or 0
    
    # Total Expenses (Payments Made)
    period_expenses = payment_date_filter(
        Payment.objects.filter(status=Payment.Status.PAID)
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # --- Gross Profit ---
    boxed_cost_qs = BoxedSale.objects.filter(sale__status=Sale.Status.ACTIVE)
    coupled_cost_qs = CoupledSale.objects.filter(sale__status=Sale.Status.ACTIVE)
    
    if filter_month:
        boxed_cost_qs = boxed_cost_qs.filter(
            sale__sale_date__month=filter_month,
            sale__sale_date__year=filter_year,
        )
        coupled_cost_qs = coupled_cost_qs.filter(
            sale__sale_date__month=filter_month,
            sale__sale_date__year=filter_year,
        )
    else:
        boxed_cost_qs = boxed_cost_qs.filter(sale__sale_date__year=filter_year)
        coupled_cost_qs = coupled_cost_qs.filter(sale__sale_date__year=filter_year)
    
    boxed_cost = boxed_cost_qs.aggregate(
        total=Sum(
            Coalesce('cost_basis', F('quantity') * F('product__inventory__weighted_average_cost'), output_field=DecimalField())
        )
    )['total'] or Decimal('0.00')
    
    coupled_cost = coupled_cost_qs.aggregate(
        total=Sum('transformation_item__unit_cost_at_transformation')
    )['total'] or Decimal('0.00')
    
    period_gross_profit = period_sales - (boxed_cost + coupled_cost)
    period_profit_margin = (period_gross_profit / period_sales * 100) if period_sales > 0 else 0
    
    # --- Charts Data ---
    # Last 7 Days Sales
    last_7_days = today - timedelta(days=6)
    sales_last_7_days = Sale.objects.filter(
        sale_date__date__gte=last_7_days, status=Sale.Status.ACTIVE
    ).annotate(day=TruncDay('sale_date')).values('day').annotate(
        total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price')
    ).order_by('day')
    
    days_labels = []
    days_data = []
    sales_dict = {entry['day'].strftime('%Y-%m-%d'): entry['total'] for entry in sales_last_7_days}
    
    for i in range(7):
        day = (last_7_days + timedelta(days=i)).strftime('%Y-%m-%d')
        days_labels.append(day)
        days_data.append(float(sales_dict.get(day) or 0))
    
    # SVG bar chart data
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
    
    # --- Top Selling Products (Period-aware) ---
    top_products_qs = Product.objects.annotate(
        total_revenue=Coalesce(
            Sum(F('boxed_sales__price') * F('boxed_sales__quantity'),
                filter=Q(boxed_sales__sale__status=Sale.Status.ACTIVE)
            ), 0.0, output_field=DecimalField()
        ) + Coalesce(
            Sum('transform_to__coupled_sales__price',
                filter=Q(transform_to__coupled_sales__sale__status=Sale.Status.ACTIVE)
            ), 0.0, output_field=DecimalField()
        )
    )
    
    if filter_month:
        top_products_qs = top_products_qs.filter(
            Q(boxed_sales__sale__sale_date__month=filter_month, boxed_sales__sale__sale_date__year=filter_year) |
            Q(transform_to__coupled_sales__sale__sale_date__month=filter_month, transform_to__coupled_sales__sale__sale_date__year=filter_year)
        )
    else:
        top_products_qs = top_products_qs.filter(
            Q(boxed_sales__sale__sale_date__year=filter_year) |
            Q(transform_to__coupled_sales__sale__sale_date__year=filter_year)
        )
    
    top_products = top_products_qs.order_by('-total_revenue').distinct()[:5]
    
    max_revenue = max([float(p.total_revenue) for p in top_products], default=1) or 1
    for p in top_products:
        p.revenue_percent = int((float(p.total_revenue) / max_revenue) * 100)
    
    # --- Sales by Category (period-aware, kept for compatibility) ---
    category_qs = BoxedSale.objects.filter(sale__status=Sale.Status.ACTIVE)
    if filter_month:
        category_qs = category_qs.filter(
            sale__sale_date__month=filter_month,
            sale__sale_date__year=filter_year,
        )
    else:
        category_qs = category_qs.filter(sale__sale_date__year=filter_year)
    
    sales_by_category = category_qs.values('product__category').annotate(
        total=Sum(F('price') * F('quantity'))
    ).order_by('-total')
    
    category_labels = [item['product__category'].title() for item in sales_by_category]
    category_data = [float(item['total']) for item in sales_by_category]
    
    # --- Recent Sales (Last 5) ---
    recent_sales = Sale.objects.filter(
        status=Sale.Status.ACTIVE
    ).select_related('customer').order_by('-sale_date')[:5]
    
    # --- Recent Deposits (Last 5) ---
    recent_deposits = Transaction.objects.filter(
        status=Transaction.Status.ACTIVE,
        transaction_type=Transaction.TransactionType.DEPOSIT,
    ).select_related('account', 'account__customer').order_by('-created_at')[:5]
    
    # --- Attention Alerts Data ---
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
    new_customers_period = Customer.objects.filter(
        created_at__month=filter_month or current_month,
        created_at__year=filter_year,
    ).count() if filter_month else Customer.objects.filter(created_at__year=filter_year).count()
    
    # --- Supply Chain ---
    pending_pos = PurchaseOrder.objects.filter(
        delivery_status=PurchaseOrder.DeliveryStatus.PENDING
    ).count()
    pending_deliveries_count = PurchaseOrder.objects.filter(
        Q(delivery_status=PurchaseOrder.DeliveryStatus.PARTIALLY_RECEIVED) |
        Q(delivery_status=PurchaseOrder.DeliveryStatus.PENDING)
    ).count()
    
    # Determine if attention panel should show
    show_attention = bool(low_stock or stockout or pending_deliveries_qs or idle_balances)
    attention_count = len(low_stock) + len(stockout) + len(pending_deliveries_qs) + len(idle_balances)
    
    hour = timezone.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 18:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    
    context = {
        'daily_sales': daily_sales,
        'monthly_sales': period_sales,
        'yearly_sales': yearly_sales,
        'monthly_expenses': period_expenses,
        'monthly_gross_profit': period_gross_profit,
        'monthly_profit_margin': period_profit_margin,
        'recent_sales': recent_sales,
        'recent_deposits': recent_deposits,
        'recent_transactions': Transaction.objects.filter(
            status=Transaction.Status.ACTIVE
        ).select_related('account', 'account__customer').order_by('-created_at')[:5],
        'low_stock_products': low_stock,
        'stockouts_count': len(stockout),
        'total_stock_value': total_stock_value,
        'total_customers': total_customers,
        'new_customers_month': new_customers_period,
        'pending_pos': pending_pos,
        'pending_deliveries': pending_deliveries_count,
        'days_labels': json.dumps(days_labels),
        'days_data': json.dumps(days_data),
        'top_products_names': json.dumps([p.modelname for p in top_products]),
        'top_products_data': json.dumps([float(p.total_revenue) for p in top_products]),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
        # New v4 context
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
