from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from branches.models import Branch
from inventory.models import Device, StatusHistory, Component, ComponentUsage
from inventory.services import (
    change_device_status,
    InvalidStatusTransition,
    install_component,
    remove_component,
    log_component,
)


class StatusTransitionServiceTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Gulele Main Branch", grade="I", employee_count=25)
        self.user = User.objects.create_user(username="tech1", password="password123", role=User.Role.IT_STAFF)
        self.device = Device.objects.create(
            serial_number="ETH-DEV-001",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.user,
            status=Device.Status.RECEIVED,
        )

    def test_valid_status_transition_succeeds_and_logs_history(self):
        updated_device = change_device_status(
            device=self.device,
            new_status=Device.Status.DIAGNOSED_FUNCTIONAL,
            user=self.user,
            note="PSU tested healthy, OS intact",
        )
        self.assertEqual(updated_device.status, Device.Status.DIAGNOSED_FUNCTIONAL)
        self.assertEqual(self.device.status_history.count(), 1)

        history = self.device.status_history.first()
        self.assertEqual(history.from_status, Device.Status.RECEIVED)
        self.assertEqual(history.to_status, Device.Status.DIAGNOSED_FUNCTIONAL)
        self.assertEqual(history.changed_by, self.user)
        self.assertEqual(history.note, "PSU tested healthy, OS intact")

    def test_invalid_status_transition_raises_exception(self):
        with self.assertRaises(InvalidStatusTransition):
            change_device_status(
                device=self.device,
                new_status=Device.Status.RETURNED_TO_BRANCH,
                user=self.user,
            )

    def test_terminal_state_disposed_cannot_transition(self):
        self.device.status = Device.Status.DISPOSED
        self.device.save(update_fields=["status"])

        with self.assertRaises(InvalidStatusTransition):
            change_device_status(
                device=self.device,
                new_status=Device.Status.RECEIVED,
                user=self.user,
            )


class ComponentLifecycleTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Addis Ketema Branch", grade="II", employee_count=15)
        self.user = User.objects.create_user(username="tech2", password="password123", role=User.Role.IT_STAFF)
        self.donor_device = Device.objects.create(
            serial_number="DONOR-PC-01",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.user,
        )
        self.target_device = Device.objects.create(
            serial_number="TARGET-PC-01",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.user,
        )
        self.component = log_component(
            source_device=self.donor_device,
            component_type=Component.ComponentType.RAM,
        )

    def test_component_install_remove_and_reuse_cycle(self):
        # 1. Initial State
        self.assertEqual(self.component.status, Component.Status.IN_STOCK)

        # 2. Install onto target device
        usage = install_component(
            component=self.component,
            device=self.target_device,
            user=self.user,
            note="Installed 8GB DDR4 RAM",
        )
        self.component.refresh_from_db()
        self.assertEqual(self.component.status, Component.Status.INSTALLED)
        self.assertIsNone(usage.removed_at)
        self.assertEqual(usage.installed_by, self.user)

        # 3. Cannot install already-installed component
        with self.assertRaises(ValueError):
            install_component(
                component=self.component,
                device=self.target_device,
                user=self.user,
            )

        # 4. Remove component from target device
        removed_usage = remove_component(component=self.component, user=self.user)
        self.component.refresh_from_db()
        self.assertEqual(self.component.status, Component.Status.IN_STOCK)
        self.assertIsNotNone(removed_usage.removed_at)
        self.assertEqual(removed_usage.removed_by, self.user)

        # 5. Cannot remove an in-stock component
        with self.assertRaises(ValueError):
            remove_component(component=self.component, user=self.user)

        # 6. Reuse component on another device
        second_target = Device.objects.create(
            serial_number="TARGET-PC-02",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.user,
        )
        new_usage = install_component(
            component=self.component,
            device=second_target,
            user=self.user,
            note="Reassigned to second device",
        )
        self.component.refresh_from_db()
        self.assertEqual(self.component.status, Component.Status.INSTALLED)
        self.assertEqual(self.component.usages.count(), 2)
        self.assertEqual(new_usage.device, second_target)


class InventoryPermissionAndViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Shiro Meda Branch", grade="III", employee_count=10)
        self.it_user = User.objects.create_user(
            username="it_staff_user",
            password="password123",
            role=User.Role.IT_STAFF,
        )
        self.manager_user = User.objects.create_user(
            username="manager_user",
            password="password123",
            role=User.Role.MANAGER,
        )
        self.device = Device.objects.create(
            serial_number="DEV-PERM-01",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.it_user,
            status=Device.Status.RECEIVED,
        )

    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get(reverse("device_list"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith("/login/"))

    def test_it_staff_can_create_device_and_logs_initial_status_history(self):
        self.client.login(username="it_staff_user", password="password123")
        response = self.client.post(reverse("device_create"), {
            "serial_number": "NEW-DEV-001",
            "tag_number": "TAG-101",
            "device_type": Device.DeviceType.PC,
            "model": "Dell OptiPlex 7080",
            "branch": self.branch.id,
            "condition_notes": "No display output",
        })
        self.assertEqual(response.status_code, 302)
        new_dev = Device.objects.get(serial_number="NEW-DEV-001")
        self.assertEqual(new_dev.logged_by, self.it_user)
        self.assertEqual(new_dev.status_history.count(), 1)
        history = new_dev.status_history.first()
        self.assertEqual(history.from_status, "")
        self.assertEqual(history.to_status, Device.Status.RECEIVED)
        self.assertEqual(history.changed_by, self.it_user)

    def test_manager_cannot_create_device_returns_403(self):
        self.client.login(username="manager_user", password="password123")
        get_response = self.client.get(reverse("device_create"))
        self.assertEqual(get_response.status_code, 403)

        post_response = self.client.post(reverse("device_create"), {
            "serial_number": "MGR-ATTEMPT-01",
            "device_type": Device.DeviceType.PC,
            "branch": self.branch.id,
        })
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(Device.objects.filter(serial_number="MGR-ATTEMPT-01").exists())

    def test_manager_cannot_change_device_status_returns_403(self):
        self.client.login(username="manager_user", password="password123")
        post_response = self.client.post(reverse("device_detail", kwargs={"pk": self.device.pk}), {
            "new_status": Device.Status.DIAGNOSED_FUNCTIONAL,
            "note": "Manager change attempt",
        })
        self.assertEqual(post_response.status_code, 403)
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, Device.Status.RECEIVED)

    def test_it_staff_component_ui_workflow(self):
        self.client.login(username="it_staff_user", password="password123")

        # 1. Log a salvaged component via UI
        create_resp = self.client.post(reverse("component_create"), {
            "source_device": self.device.pk,
            "component_type": Component.ComponentType.RAM,
        })
        self.assertEqual(create_resp.status_code, 302)
        comp = Component.objects.get(source_device=self.device)
        self.assertEqual(comp.status, Component.Status.IN_STOCK)

        # 2. View component list
        list_resp = self.client.get(reverse("component_list"))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, "Salvaged Components")
        self.assertContains(list_resp, comp.source_device.serial_number)

        # 3. Install on a second device
        dev2 = Device.objects.create(
            serial_number="DEV-PERM-02",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.it_user,
        )
        install_resp = self.client.post(
            reverse("device_install_component", kwargs={"pk": dev2.pk}),
            {"component": comp.pk, "note": "Installed RAM via UI"},
        )
        self.assertEqual(install_resp.status_code, 302)
        comp.refresh_from_db()
        self.assertEqual(comp.status, Component.Status.INSTALLED)

        # 4. Detail page reflects installed component
        detail_resp = self.client.get(reverse("device_detail", kwargs={"pk": dev2.pk}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Installed RAM via UI")

        # 5. Remove component via UI
        remove_resp = self.client.post(
            reverse("device_remove_component", kwargs={"pk": dev2.pk, "component_pk": comp.pk})
        )
        self.assertEqual(remove_resp.status_code, 302)
        comp.refresh_from_db()
        self.assertEqual(comp.status, Component.Status.IN_STOCK)
