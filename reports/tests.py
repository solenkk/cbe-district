from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from branches.models import Branch
from inventory.models import Device
from reports.models import Report
from reports.forms import ReportPeriodForm
from reports.services import generate_report


class ReportGenerationMathTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="dist_manager",
            password="password123",
            role=User.Role.MANAGER,
        )
        self.it_staff = User.objects.create_user(
            username="it_staff_rep",
            password="password123",
            role=User.Role.IT_STAFF,
        )
        self.branch_alpha = Branch.objects.create(name="Alpha Branch", grade="I", employee_count=20)
        self.branch_beta = Branch.objects.create(name="Beta Branch", grade="II", employee_count=12)

        # Branch Alpha: 4 devices in target period
        d1 = Device.objects.create(
            serial_number="ALPHA-01",
            device_type=Device.DeviceType.PC,
            branch=self.branch_alpha,
            logged_by=self.it_staff,
            status=Device.Status.REPAIRED,
        )
        Device.objects.filter(pk=d1.pk).update(date_received=date(2026, 1, 5))

        d2 = Device.objects.create(
            serial_number="ALPHA-02",
            device_type=Device.DeviceType.MONITOR,
            branch=self.branch_alpha,
            logged_by=self.it_staff,
            status=Device.Status.RETURNED_TO_BRANCH,
        )
        Device.objects.filter(pk=d2.pk).update(date_received=date(2026, 1, 10))

        d3 = Device.objects.create(
            serial_number="ALPHA-03",
            device_type=Device.DeviceType.SCANNER,
            branch=self.branch_alpha,
            logged_by=self.it_staff,
            status=Device.Status.DISPOSED,
        )
        Device.objects.filter(pk=d3.pk).update(date_received=date(2026, 1, 15))

        d4 = Device.objects.create(
            serial_number="ALPHA-04",
            device_type=Device.DeviceType.PRINTER,
            branch=self.branch_alpha,
            logged_by=self.it_staff,
            status=Device.Status.DIAGNOSED_FUNCTIONAL,
        )
        Device.objects.filter(pk=d4.pk).update(date_received=date(2026, 1, 20))

        # Device received outside target period (should be excluded)
        d5 = Device.objects.create(
            serial_number="ALPHA-OUTSIDE",
            device_type=Device.DeviceType.PC,
            branch=self.branch_alpha,
            logged_by=self.it_staff,
            status=Device.Status.REPAIRED,
        )
        Device.objects.filter(pk=d5.pk).update(date_received=date(2025, 12, 25))

    def test_report_generation_calculates_mathematically_correct_lines(self):
        report = generate_report(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            user=self.it_staff,
        )
        self.assertEqual(report.approval_status, Report.ApprovalStatus.DRAFT)
        self.assertEqual(report.generated_by, self.it_staff)

        # Verify Alpha Branch calculations
        line_alpha = report.lines.get(branch=self.branch_alpha)
        self.assertEqual(line_alpha.devices_sent, 4)
        self.assertEqual(line_alpha.devices_maintained, 2)  # REPAIRED (1) + RETURNED_TO_BRANCH (1)
        self.assertEqual(line_alpha.devices_disposed, 1)    # DISPOSED (1)
        self.assertEqual(line_alpha.discrepancy, 1)         # 4 - (2 + 1) = 1

        # Verify Beta Branch (0 devices)
        line_beta = report.lines.get(branch=self.branch_beta)
        self.assertEqual(line_beta.devices_sent, 0)
        self.assertEqual(line_beta.devices_maintained, 0)
        self.assertEqual(line_beta.devices_disposed, 0)
        self.assertEqual(line_beta.discrepancy, 0)


class ReportApprovalAndPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manager = User.objects.create_user(
            username="dist_manager2",
            password="password123",
            role=User.Role.MANAGER,
        )
        self.it_staff = User.objects.create_user(
            username="it_staff2",
            password="password123",
            role=User.Role.IT_STAFF,
        )
        self.branch = Branch.objects.create(name="Main Branch", grade="I", employee_count=30)
        self.report = generate_report(
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
            user=self.it_staff,
        )

    def test_manager_can_approve_report(self):
        self.client.login(username="dist_manager2", password="password123")
        response = self.client.post(reverse("report_approve", kwargs={"pk": self.report.pk}))
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.approval_status, Report.ApprovalStatus.APPROVED)
        self.assertEqual(self.report.approved_by, self.manager)

    def test_it_staff_cannot_approve_report_returns_403(self):
        self.client.login(username="it_staff2", password="password123")
        response = self.client.post(reverse("report_approve", kwargs={"pk": self.report.pk}))
        self.assertEqual(response.status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(self.report.approval_status, Report.ApprovalStatus.DRAFT)
        self.assertIsNone(self.report.approved_by)


class ReportPeriodFormValidationTests(TestCase):
    def test_valid_date_range_passes(self):
        form = ReportPeriodForm(data={"period_start": "2026-01-01", "period_end": "2026-01-31"})
        self.assertTrue(form.is_valid())

    def test_inverted_date_range_raises_validation_error(self):
        form = ReportPeriodForm(data={"period_start": "2026-02-01", "period_end": "2026-01-01"})
        self.assertFalse(form.is_valid())
        self.assertIn("Period start date cannot be after period end date.", form.non_field_errors())
