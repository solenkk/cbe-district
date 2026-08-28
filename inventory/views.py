from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from branches.models import Branch
from .models import Device, StatusHistory, Component, ComponentUsage
from .forms import DeviceForm, StatusChangeForm, ComponentLogForm, ComponentInstallForm
from .services import (
    change_device_status,
    InvalidStatusTransition,
    log_component,
    install_component,
    remove_component,
)


def it_staff_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != request.user.Role.IT_STAFF:
            raise PermissionDenied("Only IT Support Staff can perform this action.")
        return view_func(request, *args, **kwargs)
    return wrapper


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

    return render(request, "inventory/device_detail.html", {
        "device": device,
        "status_form": status_form,
        "installed_components": installed_components,
        "install_form": install_form,
        "error": error,
        "can_edit": request.user.role == request.user.Role.IT_STAFF,
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