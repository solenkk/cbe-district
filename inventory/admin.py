from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Device, StatusHistory, Component, ComponentUsage, DisposalRecommendation, SoftwareLicense, SoftwareInstallation


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
class DeviceAdmin(SimpleHistoryAdmin):
    list_display = ("serial_number", "device_type", "branch", "status", "date_received")
    list_filter = ("status", "device_type", "branch")
    search_fields = ("serial_number", "tag_number")
    readonly_fields = ("status",)
    inlines = [StatusHistoryInline]


@admin.register(Component)
class ComponentAdmin(SimpleHistoryAdmin):
    list_display = ("component_type", "status", "source_device", "date_logged")
    list_filter = ("status", "component_type")
    readonly_fields = ("status",)
    inlines = [ComponentUsageInline]


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("device", "branch", "from_status", "to_status", "changed_by", "timestamp")
    list_filter = ("to_status", "branch")
    search_fields = ("device__serial_number",)
    readonly_fields = ("device", "branch", "from_status", "to_status", "changed_by", "timestamp", "note")

    def has_add_permission(self, request):
        return False


@admin.register(SoftwareLicense)
class SoftwareLicenseAdmin(SimpleHistoryAdmin):
    list_display = ("name", "seat_count", "expiry_date")
    search_fields = ("name", "license_key")


@admin.register(SoftwareInstallation)
class SoftwareInstallationAdmin(admin.ModelAdmin):
    list_display = ("license", "device", "installed_at", "installed_by")
    list_filter = ("license",)


@admin.register(DisposalRecommendation)
class DisposalRecommendationAdmin(admin.ModelAdmin):
    list_display = ("device", "status", "recommended_by", "recommended_at", "reviewed_by")
    list_filter = ("status",)
    search_fields = ("device__serial_number",)
    readonly_fields = ("device", "recommended_by", "recommended_at", "reason", "status", "reviewed_by", "reviewed_at", "manager_note")

    def has_add_permission(self, request):
        return False
