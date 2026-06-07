from django.urls import path, include
from .views import *



urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('audit-log/', audit_log, name='audit_log'),
]