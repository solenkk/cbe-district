import csv
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from .models import Report
from .forms import ReportPeriodForm
from .services import generate_report


@login_required
def report_list(request):
    if request.method == "POST":
        form = ReportPeriodForm(request.POST)
        if form.is_valid():
            report = generate_report(
                period_start=form.cleaned_data["period_start"],
                period_end=form.cleaned_data["period_end"],
                user=request.user,
            )
            return redirect("report_detail", pk=report.pk)
    else:
        form = ReportPeriodForm()

    reports = Report.objects.order_by("-generated_at")
    return render(request, "reports/report_list.html", {"reports": reports, "form": form})


@login_required
def report_detail(request, pk):
    report = get_object_or_404(
        Report.objects.select_related("generated_by", "approved_by").prefetch_related("lines__branch"),
        pk=pk,
    )
    return render(request, "reports/report_detail.html", {"report": report})


@login_required
def report_export(request, pk):
    report = get_object_or_404(Report, pk=pk)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="report_{report.pk}.csv"'

    writer = csv.writer(response)
    writer.writerow(["Branch", "Devices Sent", "Maintained", "Disposed", "In Progress"])
    for line in report.lines.select_related("branch").all():
        writer.writerow([line.branch.name, line.devices_sent, line.devices_maintained, line.devices_disposed, line.discrepancy])

    return response


@login_required
@require_POST
def report_approve(request, pk):
    report = get_object_or_404(Report, pk=pk)

    if request.user.role != request.user.Role.MANAGER:
        raise PermissionDenied("Only District Managers can approve reports.")

    report.approval_status = Report.ApprovalStatus.APPROVED
    report.approved_by = request.user
    report.save(update_fields=["approval_status", "approved_by"])

    return redirect("report_detail", pk=report.pk)


@login_required
def dynamic_report(request):
    from accounts.models import User
    from branches.models import Branch
    from inventory.models import Device
    from .services import get_activity_queryset
    
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    activity = request.GET.get("activity", "")
    staff_id = request.GET.get("staff_id", "")
    branch_id = request.GET.get("branch_id", "")
    device_type = request.GET.get("device_type", "")
    serial_number = request.GET.get("serial_number", "")
    
    activities = get_activity_queryset(
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        activity=activity if activity else None,
        staff_id=staff_id if staff_id else None,
        branch_id=branch_id if branch_id else None,
        device_type=device_type if device_type else None,
        serial_number=serial_number if serial_number else None,
    )
    
    context = {
        "activities": activities,
        "date_from": date_from,
        "date_to": date_to,
        "selected_activity": activity,
        "selected_staff": staff_id,
        "selected_branch": branch_id,
        "selected_device_type": device_type,
        "serial_number": serial_number,
        "staff_members": User.objects.filter(role=User.Role.IT_STAFF),
        "branches": Branch.objects.all(),
        "device_types": Device.DeviceType.choices,
        "activity_choices": [
            ("RECEIVED", "Received"),
            ("DIAGNOSED_FUNCTIONAL", "Diagnosed — Functional"),
            ("DIAGNOSED_NOT_FUNCTIONAL", "Diagnosed — Not Functional"),
            ("REPAIRED", "Repaired (Maintained)"),
            ("RETURNED_TO_BRANCH", "Returned to Branch (Sent)"),
            ("FOR_DISPOSAL", "For Disposal"),
            ("DISPOSED", "Disposed"),
        ]
    }
    
    return render(request, "reports/dynamic_report.html", context)


@login_required
def dynamic_report_export(request):
    from .services import get_activity_queryset
    
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    activity = request.GET.get("activity", "")
    staff_id = request.GET.get("staff_id", "")
    branch_id = request.GET.get("branch_id", "")
    device_type = request.GET.get("device_type", "")
    serial_number = request.GET.get("serial_number", "")
    
    activities = get_activity_queryset(
        date_from=date_from if date_from else None,
        date_to=date_to if date_to else None,
        activity=activity if activity else None,
        staff_id=staff_id if staff_id else None,
        branch_id=branch_id if branch_id else None,
        device_type=device_type if device_type else None,
        serial_number=serial_number if serial_number else None,
    )
    
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="audit_report.csv"'

    writer = csv.writer(response)
    writer.writerow(["Date", "Activity", "Device", "Serial Number", "Device Type", "Branch", "IT Staff", "Previous Status", "New Status", "Notes"])
    
    for act in activities:
        from inventory.models import Device
        status_dict = dict(Device.Status.choices)
        
        # Determine activity label manually if possible, or just use to_status
        to_status_display = status_dict.get(act.to_status, act.to_status)
        from_status_display = status_dict.get(act.from_status, act.from_status) if act.from_status else ""
        
        activity_label = to_status_display
        if act.to_status == "RECEIVED":
            activity_label = "Received"
        elif act.to_status == "RETURNED_TO_BRANCH":
            activity_label = "Sent"
        elif act.to_status == "REPAIRED":
            activity_label = "Maintained"
        elif act.to_status == "DISPOSED":
            activity_label = "Disposed"
            
        writer.writerow([
            act.timestamp.strftime("%Y-%m-%d %H:%M"),
            activity_label,
            act.device.model,
            act.device.serial_number,
            act.device.get_device_type_display(),
            act.branch.name if act.branch else (act.device.branch.name if act.device.branch else ""),
            act.changed_by.get_full_name() or act.changed_by.username,
            from_status_display,
            to_status_display,
            act.note
        ])

    return response

