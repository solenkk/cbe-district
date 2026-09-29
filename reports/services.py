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


def get_activity_queryset(date_from=None, date_to=None, activity=None, staff_id=None, branch_id=None, device_type=None, serial_number=None):
    from inventory.models import StatusHistory, Device
    
    qs = StatusHistory.objects.select_related("device", "device__branch", "branch", "changed_by").all()
    
    if date_from:
        qs = qs.filter(timestamp__gte=date_from)
    if date_to:
        qs = qs.filter(timestamp__date__lte=date_to)
        
    if branch_id:
        qs = qs.filter(branch_id=branch_id)
        
    if staff_id:
        qs = qs.filter(changed_by_id=staff_id)
        
    if device_type:
        qs = qs.filter(device__device_type=device_type)
        
    if serial_number:
        qs = qs.filter(device__serial_number__icontains=serial_number)
        
    if activity:
        if activity == "SENT":
            qs = qs.filter(to_status=Device.Status.RETURNED_TO_BRANCH)
        elif activity == "MAINTAINED":
            qs = qs.filter(to_status=Device.Status.REPAIRED)
        else:
            qs = qs.filter(to_status=activity)

    return qs.order_by("-timestamp")