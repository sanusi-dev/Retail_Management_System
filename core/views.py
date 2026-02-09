
from django.db.models import Sum, Count, F, Q, DecimalField, Value
from django.db.models.functions import TruncMonth, TruncDay, Coalesce
from django.utils import timezone
from datetime import timedelta
from customer.models import Sale, Customer, Transaction, BoxedSale, CoupledSale
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
    
    # --- Financial Metrics ---
    # Total Sales (Revenue)
    daily_sales = Sale.objects.filter(sale_date__date=today, status=Sale.Status.ACTIVE).aggregate(total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price'))['total'] or 0
    monthly_sales = Sale.objects.filter(sale_date__month=current_month, sale_date__year=current_year, status=Sale.Status.ACTIVE).aggregate(total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price'))['total'] or 0
    yearly_sales = Sale.objects.filter(sale_date__year=current_year, status=Sale.Status.ACTIVE).aggregate(total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price'))['total'] or 0
    
    # Total Expenses (Payments Made)
    monthly_expenses = Payment.objects.filter(payment_date__month=current_month, payment_date__year=current_year, status=Payment.Status.PAID).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # --- Gross Profit (Estimated) ---
    # Boxed Sales Cost (using current WAC)
    boxed_cost = BoxedSale.objects.filter(
        sale__sale_date__month=current_month, 
        sale__sale_date__year=current_year, 
        sale__status=Sale.Status.ACTIVE
    ).aggregate(
        total=Sum(F('quantity') * F('product__inventory__weighted_average_cost'), output_field=DecimalField())
    )['total'] or Decimal('0.00')

    # Coupled Sales Cost (using unit_cost_at_transformation)
    coupled_cost = CoupledSale.objects.filter(
        sale__sale_date__month=current_month, 
        sale__sale_date__year=current_year, 
        sale__status=Sale.Status.ACTIVE
    ).aggregate(
        total=Sum('transformation_item__unit_cost_at_transformation')
    )['total'] or Decimal('0.00')

    monthly_gross_profit = monthly_sales - (boxed_cost + coupled_cost)
    monthly_profit_margin = (monthly_gross_profit / monthly_sales * 100) if monthly_sales > 0 else 0

    # --- Charts Data ---
    # Last 7 Days Sales
    last_7_days = today - timedelta(days=6)
    sales_last_7_days = Sale.objects.filter(sale_date__date__gte=last_7_days, status=Sale.Status.ACTIVE)\
        .annotate(day=TruncDay('sale_date'))\
        .values('day')\
        .annotate(total=Sum(F('boxed_sales__price') * F('boxed_sales__quantity')) + Sum('coupled_sales__price'))\
        .order_by('day')
        
    days_labels = []
    days_data = []
    
    # Create a dict for easy lookup
    sales_dict = {entry['day'].strftime('%Y-%m-%d'): entry['total'] for entry in sales_last_7_days}
    
    for i in range(7):
        day = (last_7_days + timedelta(days=i)).strftime('%Y-%m-%d')
        days_labels.append(day)
        days_data.append(float(sales_dict.get(day) or 0))

    # --- Top Selling Products (Current Month) ---
    top_products = Product.objects.annotate(
        total_revenue=Coalesce(
            Sum(F('boxed_sales__price') * F('boxed_sales__quantity'), 
                filter=Q(boxed_sales__sale__sale_date__month=current_month, boxed_sales__sale__sale_date__year=current_year, boxed_sales__sale__status=Sale.Status.ACTIVE)
            ), 0.0, output_field=DecimalField()
        ) + Coalesce(
            Sum('transform_to__coupled_sales__price', 
                filter=Q(transform_to__coupled_sales__sale__sale_date__month=current_month, transform_to__coupled_sales__sale__sale_date__year=current_year, transform_to__coupled_sales__sale__status=Sale.Status.ACTIVE)
            ), 0.0, output_field=DecimalField()
        )
    ).order_by('-total_revenue')[:5]

    top_products_names = [p.modelname for p in top_products]
    top_products_data = [float(p.total_revenue) for p in top_products]

    # --- Sales by Category ---
    sales_by_category = BoxedSale.objects.filter(
        sale__sale_date__month=current_month, 
        sale__sale_date__year=current_year, 
        sale__status=Sale.Status.ACTIVE
    ).values('product__category').annotate(
        total=Sum(F('price') * F('quantity'))
    ).order_by('-total')
    
    # Simplified for chart
    category_labels = [item['product__category'].title() for item in sales_by_category]
    category_data = [float(item['total']) for item in sales_by_category]


    # --- Recent Sales (Last 5) ---
    recent_sales = Sale.objects.filter(status=Sale.Status.ACTIVE).select_related('customer').order_by('-sale_date')[:5]

    # --- Recent Transactions (Last 5) ---
    recent_transactions = Transaction.objects.filter(status=Transaction.Status.ACTIVE).select_related('account', 'account__customer').order_by('-created_at')[:5]

    # --- Inventory Metrics ---
    # Low Stock Products (assuming threshold < 5)
    low_stock_products = Inventory.objects.filter(quantity__lt=5).select_related('product', 'product__brand').order_by('quantity')[:5]
    
    # Stockouts
    stockouts_count = Inventory.objects.filter(quantity=0).count()

    # Total Stock Value
    total_stock_value = Inventory.objects.aggregate(
        total=Sum(F('quantity') * F('weighted_average_cost'))
    )['total'] or 0

    # --- Customer Metrics ---
    total_customers = Customer.objects.count()
    new_customers_month = Customer.objects.filter(created_at__month=current_month, created_at__year=current_year).count()
    
    # --- Supply Chain ---
    pending_pos = PurchaseOrder.objects.filter(delivery_status=PurchaseOrder.DeliveryStatus.PENDING).count()
    pending_deliveries = PurchaseOrder.objects.filter(
        Q(delivery_status=PurchaseOrder.DeliveryStatus.PARTIALLY_RECEIVED) | 
        Q(delivery_status=PurchaseOrder.DeliveryStatus.PENDING)
    ).count()

    context = {
        'daily_sales': daily_sales,
        'monthly_sales': monthly_sales,
        'yearly_sales': yearly_sales,
        'monthly_expenses': monthly_expenses,
        'monthly_gross_profit': monthly_gross_profit,
        'monthly_profit_margin': monthly_profit_margin,
        'recent_sales': recent_sales,
        'recent_transactions': recent_transactions,
        'low_stock_products': low_stock_products,
        'stockouts_count': stockouts_count,
        'total_stock_value': total_stock_value,
        'total_customers': total_customers,
        'new_customers_month': new_customers_month,
        'pending_pos': pending_pos,
        'pending_deliveries': pending_deliveries,
        'days_labels': json.dumps(days_labels),
        'days_data': json.dumps(days_data),
        'top_products_names': json.dumps(top_products_names),
        'top_products_data': json.dumps(top_products_data),
        'category_labels': json.dumps(category_labels),
        'category_data': json.dumps(category_data),
    }
    

    if request.htmx:
        return HttpResponse(
            render_block_to_string(
                "dashboard.html",
                "content",
                context,
                request=request,
            )
        )

    return render(request, "dashboard.html", context)