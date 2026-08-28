from django.db import models
from django.conf import settings
from branches.models import Branch


class Report(models.Model):
    class ApprovalStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"

    period_start = models.DateField()
    period_end = models.DateField()
    approval_status = models.CharField(
        max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.DRAFT
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_generated"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_approved",
        null=True, blank=True
    )

    def __str__(self):
        return f"Report {self.period_start} to {self.period_end} ({self.get_approval_status_display()})"


class ReportLine(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="lines")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="report_lines")

    devices_sent = models.PositiveIntegerField()
    devices_maintained = models.PositiveIntegerField()
    devices_disposed = models.PositiveIntegerField()
    discrepancy = models.IntegerField(verbose_name="In Progress")

    class Meta:
        unique_together = ("report", "branch")

    def __str__(self):
        return f"{self.branch.name} — {self.report}"