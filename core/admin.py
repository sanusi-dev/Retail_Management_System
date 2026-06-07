from django.contrib import admin
from core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "object_repr", "object_type", "ip_address"]
    list_filter = ["action", "object_type", "timestamp"]
    search_fields = ["action", "object_repr", "object_type", "user__username", "user__first_name", "user__last_name"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]
    date_hierarchy = "timestamp"
    ordering = ["-timestamp"]
