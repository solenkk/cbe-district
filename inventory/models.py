from django.db import models
from django.conf import settings
from branches.models import Branch


class Device(models.Model):
    class DeviceType(models.TextChoices):
        PC = "PC", "PC"
        MONITOR = "MONITOR", "Monitor"
        SCANNER = "SCANNER", "Scanner"
        PRINTER = "PRINTER", "Printer"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        RECEIVED = "RECEIVED", "Received"
        DIAGNOSED_FUNCTIONAL = "DIAGNOSED_FUNCTIONAL", "Diagnosed — Functional"
        DIAGNOSED_NOT_FUNCTIONAL = "DIAGNOSED_NOT_FUNCTIONAL", "Diagnosed — Not Functional"
        REPAIRED = "REPAIRED", "Repaired"
        RETURNED_TO_BRANCH = "RETURNED_TO_BRANCH", "Returned to Branch"
        FOR_DISPOSAL = "FOR_DISPOSAL", "For Disposal"
        DISPOSED = "DISPOSED", "Disposed"

    serial_number = models.CharField(max_length=100, unique=True)
    tag_number = models.CharField(max_length=100, blank=True)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    model = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.RECEIVED)
    condition_notes = models.TextField(blank=True)
    date_received = models.DateField(auto_now_add=True)

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="devices")
    logged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="logged_devices")

    def __str__(self):
        return f"{self.serial_number} ({self.get_status_display()})"


class StatusHistory(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Status history"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.device.serial_number}: {self.from_status} → {self.to_status}"

class Component(models.Model):
    class ComponentType(models.TextChoices):
        RAM = "RAM", "RAM"
        HDD = "HDD", "Hard Disk"
        SSD = "SSD", "SSD"
        PRINTER_PART = "PRINTER_PART", "Printer Component"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        IN_STOCK = "IN_STOCK", "In Stock"
        INSTALLED = "INSTALLED", "Installed"
        DISPOSED = "DISPOSED", "Disposed"

    component_type = models.CharField(max_length=20, choices=ComponentType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_STOCK)
    date_logged = models.DateField(auto_now_add=True)

    source_device = models.ForeignKey(
        Device, on_delete=models.PROTECT, related_name="salvaged_components"
    )

    def __str__(self):
        return f"{self.get_component_type_display()} from {self.source_device.serial_number}"


class ComponentUsage(models.Model):
    component = models.ForeignKey(Component, on_delete=models.PROTECT, related_name="usages")
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="components_used")

    installed_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="components_installed"
    )
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="components_removed",
        null=True, blank=True
    )
    installation_note = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Component usages"
        ordering = ["-installed_at"]

    def __str__(self):
        status = "installed" if self.removed_at is None else "removed"
        return f"{self.component} → {self.device.serial_number} ({status})"