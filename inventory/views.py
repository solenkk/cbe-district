from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
import json
from django.db import transaction
from django.db.models import Q, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from branches.models import Branch
from .models import Device, StatusHistory, Component, ComponentUsage, DisposalRecommendation
from .forms import DeviceForm, StatusChangeForm, ComponentLogForm, ComponentInstallForm, DisposalRecommendationForm, DisposalReviewForm
from .services import (
    change_device_status,
    InvalidStatusTransition,
    log_component,
    install_component,
    remove_component,
    create_disposal_recommendation,
    approve_disposal_recommendation,
    reject_disposal_recommendation,
)


def it_staff_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != request.user.Role.IT_STAFF:
            raise PermissionDenied("Only IT Support Staff can perform this action.")
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
def dashboard(request):
    context = {}
    context["device_count"] = Device.objects.count()
    context["recent_devices_count"] = Device.objects.filter(status=Device.Status.RECEIVED).count()
    context["component_count"] = Component.objects.count()
    context["in_stock_count"] = Component.objects.filter(status=Component.Status.IN_STOCK).count()

    context["active_devices_count"] = Device.objects.filter(status=Device.Status.RETURNED_TO_BRANCH).count()
    context["maintenance_devices_count"] = Device.objects.filter(status__in=[
        Device.Status.RECEIVED, 
        Device.Status.DIAGNOSED_FUNCTIONAL, 
        Device.Status.DIAGNOSED_NOT_FUNCTIONAL, 
        Device.Status.REPAIRED
    ]).count()
    context["disposed_devices_count"] = Device.objects.filter(status__in=[
        Device.Status.DISPOSED,
        Device.Status.FOR_DISPOSAL
    ]).count()

    context["attention_devices"] = Device.objects.exclude(status__in=[
        Device.Status.RETURNED_TO_BRANCH, 
        Device.Status.DISPOSED
    ]).select_related("branch").order_by("-date_received")[:5]

    context["recent_activity"] = StatusHistory.objects.select_related(
        "device", "changed_by"
    ).order_by("-timestamp")[:6]
    
    context["recent_devices"] = Device.objects.select_related("branch").order_by("-date_received")[:5]

    if request.user.role == request.user.Role.MANAGER:
        context["pending_disposals_count"] = DisposalRecommendation.objects.filter(status=DisposalRecommendation.Status.PENDING).count()
    else:
        context["my_recent_activity"] = StatusHistory.objects.filter(changed_by=request.user).order_by("-timestamp")[:5]

    devices_by_status = list(Device.objects.values('status').annotate(count=Count('status')))
    status_labels = [dict(Device.Status.choices).get(d['status'], d['status']) for d in devices_by_status]
    status_counts = [d['count'] for d in devices_by_status]
    context["chart_labels"] = json.dumps(status_labels)
    context["chart_data"] = json.dumps(status_counts)

    return render(request, "inventory/dashboard.html", context)


@login_required
def device_list(request):
    devices = Device.objects.select_related("branch").order_by("-date_received")

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    device_type = request.GET.get("device_type", "")
    branch_id = request.GET.get("branch", "")

    if query:
        devices = devices.filter(
            Q(serial_number__icontains=query) | Q(tag_number__icontains=query)
        )
    if status:
        if "," in status:
            devices = devices.filter(status__in=status.split(","))
        else:
            devices = devices.filter(status=status)
    if device_type:
        devices = devices.filter(device_type=device_type)
    if branch_id:
        devices = devices.filter(branch_id=branch_id)

    context = {
        "devices": devices,
        "query": query,
        "selected_status": status,
        "selected_device_type": device_type,
        "selected_branch": branch_id,
        "status_choices": Device.Status.choices,
        "device_type_choices": Device.DeviceType.choices,
        "branches": Branch.objects.all(),
    }
    return render(request, "inventory/device_list.html", context)


@it_staff_required
@transaction.atomic
def device_create(request):
    if request.method == "POST":
        form = DeviceForm(request.POST)
        if form.is_valid():
            device = form.save(commit=False)
            device.logged_by = request.user
            device.save()
            StatusHistory.objects.create(
                device=device,
                branch=device.branch,
                from_status="",
                to_status=device.status,
                changed_by=request.user,
                note="",
            )
            return redirect("device_detail", pk=device.pk)
    else:
        form = DeviceForm()
    return render(request, "inventory/device_form.html", {"form": form})


@login_required
def device_detail(request, pk):
    device = get_object_or_404(Device.objects.select_related("branch", "logged_by"), pk=pk)
    error = None

    if request.method == "POST":
        if request.user.role != request.user.Role.IT_STAFF:
            raise PermissionDenied("Only IT Support Staff can change device status.")

        status_form = StatusChangeForm(request.POST, device=device)
        if status_form.is_valid():
            try:
                change_device_status(
                    device=device,
                    new_status=status_form.cleaned_data["new_status"],
                    user=request.user,
                    note=status_form.cleaned_data["note"],
                )
                return redirect("device_detail", pk=device.pk)
            except InvalidStatusTransition as e:
                error = str(e)
    else:
        status_form = StatusChangeForm(device=device)

    installed_components = device.components_used.filter(
        removed_at__isnull=True
    ).select_related("component", "component__source_device", "installed_by")
    install_form = ComponentInstallForm()
    
    pending_recommendation = device.disposal_recommendations.filter(status=DisposalRecommendation.Status.PENDING).first()
    rejected_recommendation = device.disposal_recommendations.filter(status=DisposalRecommendation.Status.REJECTED).order_by("-reviewed_at").first()

    return render(request, "inventory/device_detail.html", {
        "device": device,
        "status_form": status_form,
        "installed_components": installed_components,
        "install_form": install_form,
        "error": error,
        "can_edit": request.user.role == request.user.Role.IT_STAFF,
        "pending_recommendation": pending_recommendation,
        "rejected_recommendation": rejected_recommendation,
    })


@it_staff_required
@require_POST
def device_install_component(request, pk):
    device = get_object_or_404(Device, pk=pk)
    form = ComponentInstallForm(request.POST)
    if form.is_valid():
        try:
            install_component(
                component=form.cleaned_data["component"],
                device=device,
                user=request.user,
                note=form.cleaned_data["note"],
            )
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("device_detail", pk=device.pk)


@it_staff_required
@require_POST
def device_remove_component(request, pk, component_pk):
    component = get_object_or_404(Component, pk=component_pk)
    try:
        remove_component(component=component, user=request.user)
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("device_detail", pk=pk)


@login_required
def device_history(request, pk):
    device = get_object_or_404(
        Device.objects.prefetch_related("status_history__changed_by"),
        pk=pk,
    )
    return render(request, "inventory/device_history.html", {"device": device})


@login_required
def device_sleeve(request, pk):
    device = get_object_or_404(Device.objects.select_related("branch", "logged_by"), pk=pk)
    last_entry = device.status_history.first()
    return render(request, "inventory/device_sleeve.html", {"device": device, "last_entry": last_entry})


@login_required
def component_list(request):
    components = Component.objects.select_related("source_device", "source_device__branch").order_by("-date_logged")

    status = request.GET.get("status", "")
    component_type = request.GET.get("component_type", "")

    if status:
        components = components.filter(status=status)
    if component_type:
        components = components.filter(component_type=component_type)

    context = {
        "components": components,
        "selected_status": status,
        "selected_component_type": component_type,
        "status_choices": Component.Status.choices,
        "component_type_choices": Component.ComponentType.choices,
    }
    return render(request, "inventory/component_list.html", context)


@it_staff_required
def component_create(request):
    if request.method == "POST":
        form = ComponentLogForm(request.POST)
        if form.is_valid():
            log_component(
                source_device=form.cleaned_data["source_device"],
                component_type=form.cleaned_data["component_type"],
            )
            return redirect("component_list")
    else:
        initial_device = request.GET.get("device")
        form = ComponentLogForm(initial={"source_device": initial_device} if initial_device else None)

    return render(request, "inventory/component_form.html", {"form": form})


@it_staff_required
def disposal_recommendation_create(request, pk):
    device = get_object_or_404(Device, pk=pk)
    
    if device.status != Device.Status.FOR_DISPOSAL:
        messages.error(request, "Device must be FOR_DISPOSAL to recommend disposal.")
        return redirect("device_detail", pk=device.pk)
        
    if request.method == "POST":
        form = DisposalRecommendationForm(request.POST)
        if form.is_valid():
            try:
                create_disposal_recommendation(
                    device=device,
                    user=request.user,
                    reason=form.cleaned_data["reason"]
                )
                messages.success(request, "Disposal recommendation submitted.")
                return redirect("device_detail", pk=device.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = DisposalRecommendationForm()
        
    return render(request, "inventory/disposal_recommendation_form.html", {"form": form, "device": device})


@login_required
def disposal_recommendation_list(request):
    if request.user.role != request.user.Role.MANAGER:
        raise PermissionDenied("Only District Managers can view pending disposal recommendations.")
        
    recommendations = DisposalRecommendation.objects.filter(
        status=DisposalRecommendation.Status.PENDING
    ).select_related("device", "device__branch", "recommended_by")
    
    return render(request, "inventory/disposal_recommendation_list.html", {"recommendations": recommendations})


@login_required
def disposal_recommendation_review(request, pk):
    if request.user.role != request.user.Role.MANAGER:
        raise PermissionDenied("Only District Managers can review disposal recommendations.")
        
    recommendation = get_object_or_404(
        DisposalRecommendation.objects.select_related("device", "device__branch", "recommended_by"), 
        pk=pk
    )
    
    if recommendation.status != DisposalRecommendation.Status.PENDING:
        messages.info(request, "This recommendation has already been reviewed.")
        return redirect("disposal_recommendation_list")
        
    if request.method == "POST":
        form = DisposalReviewForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data["action"]
            note = form.cleaned_data["note"]
            
            try:
                if action == "APPROVE":
                    approve_disposal_recommendation(
                        recommendation=recommendation, user=request.user, note=note
                    )
                    messages.success(request, "Disposal approved.")
                else:
                    reject_disposal_recommendation(
                        recommendation=recommendation, user=request.user, note=note
                    )
                    messages.success(request, "Disposal rejected.")
                return redirect("disposal_recommendation_list")
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = DisposalReviewForm()
        
    return render(request, "inventory/disposal_recommendation_review.html", {
        "recommendation": recommendation,
        "form": form
    })