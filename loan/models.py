from django.db import models
import uuid
from customer.models import Customer, Sale
from account.models import CustomUser
from django.db.models import Q, CheckConstraint, F
from django.utils import timezone


class Loan(models.Model):
    LOAN_TYPE = ['sales loan', 'normal loan']
    STATUS = ['active', 'paid', 'overdue', 'wtitten off', 'cancelled']

    loan_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='customer_loans')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='loan_sales', null=True)
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPE)
    principal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    loan_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='active', blank=True)
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.loan_id
    
    class Meta:
        constraints = [
            CheckConstraint (
                check= (
                    Q(loan_type='sales loan', sale_id__isnull=False) |
                    Q(loan_type='normal loan', sale_id__isnull=True)
                ), name= 'chk_loan_type_sale_logic'
            ),

            CheckConstraint (
                check= Q(principal_amount__gt=0), 
                name='chk_positive_principal_amount'
            ),
        
            CheckConstraint (
                check= (Q(due_date__gte=F('loan_date'))), 
                name= 'chk_due_date_logic'
            ),
        ]


class LoanRepayments(models.Model):
    PAYMENT_METHOD = ['cash', 'transfer']

    def generate_txn_ref(self):
        return f"LP-TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    repayment_id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name='loan_repayments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    repayment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, default='cash', choices=PAYMENT_METHOD)
    trxn_ref = models.CharField(max_length=50, editable=False, default=generate_txn_ref, unique=True)
    remark = models.TextField(blank=True, default='')
    create_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    create_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)
    update_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL)

    def __str__(self):
        return self.trxn_ref

    class Meta:
        constraints = [
            CheckConstraint (
                check=(Q(amount__gt=0)), 
                name='chk_positive_repayment_amount'
            ),
        ]