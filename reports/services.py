# reports/services.py

from django.db import transaction
from django.db.models import Count, Q
from branches.models import Branch
from inventory.models import Device
from .models import Report, ReportLine


@transaction.atomic
def generate_report(*, period_start, period_end, user) -> Report:
    report = Report.objects.create(
        period_start=period_start,
        period_end=period_end,
        generated_by=user,
    )

    branches_with_counts = Branch.objects.annotate(
        devices_sent=Count(
            "devices",
            filter=Q(
                devices__date_received__gte=period_start,
                devices__date_received__lte=period_end,
            ),
        ),
        devices_maintained=Count(
            "devices",
            filter=Q(
                devices__date_received__gte=period_start,
                devices__date_received__lte=period_end,
                devices__status__in=[Device.Status.REPAIRED, Device.Status.RETURNED_TO_BRANCH],
            ),
        ),
        devices_disposed=Count(
            "devices",
            filter=Q(
                devices__date_received__gte=period_start,
                devices__date_received__lte=period_end,
                devices__status=Device.Status.DISPOSED,
            ),
        ),
    )

    lines = [
        ReportLine(
            report=report,
            branch=b,
            devices_sent=b.devices_sent,
            devices_maintained=b.devices_maintained,
            devices_disposed=b.devices_disposed,
            discrepancy=b.devices_sent - (b.devices_maintained + b.devices_disposed),
        )
        for b in branches_with_counts
    ]
    ReportLine.objects.bulk_create(lines)

    return report