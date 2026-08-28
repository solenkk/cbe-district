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

