from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from branches.models import Branch
from inventory.models import Device, StatusHistory
from reports.services import get_activity_queryset
from django.utils import timezone
import datetime

class DynamicReportTests(TestCase):
    def setUp(self):
        self.branch1 = Branch.objects.create(name="Branch 1", grade="I", employee_count=10)
        self.branch2 = Branch.objects.create(name="Branch 2", grade="I", employee_count=10)
        self.staff1 = User.objects.create_user(username="staff1", password="password", role=User.Role.IT_STAFF)
        self.staff2 = User.objects.create_user(username="staff2", password="password", role=User.Role.IT_STAFF)
        
        self.device1 = Device.objects.create(serial_number="SN001", device_type="PC", branch=self.branch1, logged_by=self.staff1, status=Device.Status.RECEIVED)
        self.device2 = Device.objects.create(serial_number="SN002", device_type="PC", branch=self.branch2, logged_by=self.staff2, status=Device.Status.RECEIVED)
        
        StatusHistory.objects.create(device=self.device1, branch=self.branch1, to_status=Device.Status.RECEIVED, changed_by=self.staff1)
        StatusHistory.objects.create(device=self.device1, branch=self.branch1, to_status=Device.Status.REPAIRED, changed_by=self.staff1)
        StatusHistory.objects.create(device=self.device2, branch=self.branch2, to_status=Device.Status.RECEIVED, changed_by=self.staff2)
        StatusHistory.objects.create(device=self.device2, branch=self.branch2, to_status=Device.Status.RETURNED_TO_BRANCH, changed_by=self.staff2)

    def test_filter_by_activity(self):
        qs = get_activity_queryset(activity="MAINTAINED")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().device, self.device1)
        
        qs = get_activity_queryset(activity="RECEIVED")
        self.assertEqual(qs.count(), 2)

    def test_filter_by_staff(self):
        qs = get_activity_queryset(staff_id=self.staff1.id)
        self.assertEqual(qs.count(), 2)
        
        qs = get_activity_queryset(staff_id=self.staff2.id)
        self.assertEqual(qs.count(), 2)

    def test_filter_by_branch(self):
        qs = get_activity_queryset(branch_id=self.branch1.id)
        self.assertEqual(qs.count(), 2)

    def test_csv_export(self):
        self.client.login(username="staff1", password="password")
        url = reverse("dynamic_report_export")
        response = self.client.get(url, {"activity": "MAINTAINED", "staff_id": self.staff1.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("Maintained", content)
        self.assertIn("SN001", content)
        self.assertNotIn("SN002", content)
