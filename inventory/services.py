# inventory/services.py

from django.db import transaction
from django.utils import timezone
from .models import Device, StatusHistory, Component, ComponentUsage


DEVICE_STATUS_TRANSITIONS = {
    Device.Status.RECEIVED: {
        Device.Status.DIAGNOSED_FUNCTIONAL,
        Device.Status.DIAGNOSED_NOT_FUNCTIONAL,
    },
    Device.Status.DIAGNOSED_FUNCTIONAL: {
        Device.Status.REPAIRED,
    },
    Device.Status.DIAGNOSED_NOT_FUNCTIONAL: {
        Device.Status.FOR_DISPOSAL,
    },
    Device.Status.REPAIRED: {
        Device.Status.RETURNED_TO_BRANCH,
    },
    Device.Status.FOR_DISPOSAL: {
        Device.Status.DISPOSED,
    },
    Device.Status.RETURNED_TO_BRANCH: {Device.Status.RECEIVED},
    Device.Status.DISPOSED: set(),  # terminal state
}


class InvalidStatusTransition(Exception):
    pass


@transaction.atomic
def change_device_status(*, device: Device, new_status: str, user, note: str = "") -> Device:
    allowed_next_statuses = DEVICE_STATUS_TRANSITIONS.get(device.status, set())

    if new_status not in allowed_next_statuses:
        raise InvalidStatusTransition(
            f"Cannot move device from '{device.status}' to '{new_status}'. "
            f"Allowed: {allowed_next_statuses or 'none — this is a terminal state'}"
        )

    old_status = device.status
    device.status = new_status
    device.save(update_fields=["status"])

    StatusHistory.objects.create(
        device=device,
        from_status=old_status,
        to_status=new_status,
        changed_by=user,
        note=note,
    )

    return device


def log_component(*, source_device: Device, component_type: str) -> Component:
    return Component.objects.create(
        source_device=source_device,
        component_type=component_type,
        status=Component.Status.IN_STOCK,
    )


@transaction.atomic
def install_component(*, component: Component, device: Device, user, note: str = "") -> ComponentUsage:
    if component.status != Component.Status.IN_STOCK:
        raise ValueError(
            f"Component is '{component.status}', not IN_STOCK — cannot install."
        )

    usage = ComponentUsage.objects.create(
        component=component,
        device=device,
        installed_by=user,
        installation_note=note,
    )

    component.status = Component.Status.INSTALLED
    component.save(update_fields=["status"])

    return usage


@transaction.atomic
def remove_component(*, component: Component, user) -> ComponentUsage:
    usage = component.usages.filter(removed_at__isnull=True).first()

    if usage is None:
        raise ValueError("This component has no active installation to remove.")

    usage.removed_at = timezone.now()
    usage.removed_by = user
    usage.save(update_fields=["removed_at", "removed_by"])

    component.status = Component.Status.IN_STOCK
    component.save(update_fields=["status"])

    return usage