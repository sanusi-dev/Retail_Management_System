from django.db import models
import uuid
from customer.models import Customer, Sale
from account.models import CustomUser
from django.db.models import Q, CheckConstraint, F
from django.utils import timezone


class Loan(models.Model):
    LOAN_TYPE = [
        ('sl', 'Sales Loan'),
        ('nl', 'Normal Loan'),
    ]

    STATUS = [
        ('active', 'Active'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('wtitten off', 'Written Off'),
        ('cancelled', 'Cancelled'),
    ]

    loan_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='customer_loan')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='loan_sale', null=True)
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPE)
    principal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    loan_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='active', blank=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    
    class Meta:
        constraints = [
            CheckConstraint (
                check= (
                    Q(loan_type='SL', sale_id__isnull=False) |
                    Q(loan_type='NL', sale_id__isnull=True)
                ), name= 'chk_loan_type_sale_logic'
            ),

            CheckConstraint (
                check= Q(principal_amount__gt=0), name='chk_positive_principal_amount'
            ),
        
            CheckConstraint (
                check= (
                    Q(due_date__gte=F('loan_date'))
                ), name= 'chk_due_date_logic'
            ),
        ]

class LoanRepayments(models.Model):
    PAYMENT_METHOD = [
        ('cash', 'Cash'),
        ('transfer', 'Bank Transfer'),
    ]

    def generate_txn_ref(self):
        return f"TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    repayment_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name='loan_repayment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, default='cash', choices=PAYMENT_METHOD)
    trxn_ref = models.CharField(max_length=50, editable=False, default=generate_txn_ref)
    remark = models.TextField(blank=True, default='')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    class Meta:
        constraints = [
            CheckConstraint (
                check=(Q(amount__gt=0)), 
                name='chk_positive_repayment_amount'
            ),
        ]