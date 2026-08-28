from django.contrib import admin
from .models import Device, StatusHistory, Component, ComponentUsage


class StatusHistoryInline(admin.TabularInline):
    model = StatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "timestamp", "note")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class ComponentUsageInline(admin.TabularInline):
    model = ComponentUsage
    fk_name = "component"
    extra = 0
    readonly_fields = ("device", "installed_at", "removed_at", "installed_by", "removed_by")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "device_type", "branch", "status", "date_received")
    list_filter = ("status", "device_type", "branch")
    search_fields = ("serial_number", "tag_number")
    readonly_fields = ("status",)
    inlines = [StatusHistoryInline]


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ("component_type", "status", "source_device", "date_logged")
    list_filter = ("status", "component_type")
    readonly_fields = ("status",)
    inlines = [ComponentUsageInline]
