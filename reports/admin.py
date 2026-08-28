from django.contrib import admin
from .models import Report, ReportLine


class ReportLineInline(admin.TabularInline):
    model = ReportLine
    extra = 0
    readonly_fields = ("branch", "devices_sent", "devices_maintained", "devices_disposed", "discrepancy")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("period_start", "period_end", "approval_status", "generated_by", "generated_at")
    list_filter = ("approval_status",)
    inlines = [ReportLineInline]