from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from branches.models import Branch
from inventory.models import Device, StatusHistory, DisposalRecommendation
from inventory.services import create_disposal_recommendation, approve_disposal_recommendation


class DisposalWorkflowTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Test Branch", grade="I", employee_count=10)
        self.staff = User.objects.create_user(username="staff", password="password", role=User.Role.IT_STAFF)
        self.manager = User.objects.create_user(username="manager", password="password", role=User.Role.MANAGER)
        
        self.device = Device.objects.create(
            serial_number="TEST1234",
            device_type=Device.DeviceType.PC,
            branch=self.branch,
            logged_by=self.staff,
            status=Device.Status.FOR_DISPOSAL
        )

    def test_it_staff_recommend_disposal(self):
        self.client.login(username="staff", password="password")
        url = reverse("disposal_recommendation_create", args=[self.device.pk])
        response = self.client.post(url, {"reason": "Completely broken"})
        self.assertEqual(response.status_code, 302)
        
        rec = DisposalRecommendation.objects.get(device=self.device)
        self.assertEqual(rec.status, DisposalRecommendation.Status.PENDING)
        self.assertEqual(rec.recommended_by, self.staff)

    def test_manager_approve_disposal(self):
        rec = create_disposal_recommendation(device=self.device, user=self.staff, reason="Broken")
        
        self.client.login(username="manager", password="password")
        url = reverse("disposal_recommendation_review", args=[rec.pk])
        response = self.client.post(url, {"action": "APPROVE", "note": "Approved."})
        self.assertEqual(response.status_code, 302)
        
        rec.refresh_from_db()
        self.assertEqual(rec.status, DisposalRecommendation.Status.APPROVED)
        
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, Device.Status.DISPOSED)
        
        history = StatusHistory.objects.filter(device=self.device).order_by("-timestamp").first()
        self.assertEqual(history.to_status, Device.Status.DISPOSED)
        self.assertEqual(history.branch, self.branch)

    def test_it_staff_cannot_approve_disposal(self):
        rec = create_disposal_recommendation(device=self.device, user=self.staff, reason="Broken")
        
        self.client.login(username="staff", password="password")
        url = reverse("disposal_recommendation_review", args=[rec.pk])
        response = self.client.post(url, {"action": "APPROVE", "note": "Approved."})
        self.assertEqual(response.status_code, 403)
        
        self.device.refresh_from_db()
        self.assertNotEqual(self.device.status, Device.Status.DISPOSED)

    def test_manager_reject_disposal(self):
        rec = create_disposal_recommendation(device=self.device, user=self.staff, reason="Broken")
        
        self.client.login(username="manager", password="password")
        url = reverse("disposal_recommendation_review", args=[rec.pk])
        response = self.client.post(url, {"action": "REJECT", "note": "Fix it."})
        self.assertEqual(response.status_code, 302)
        
        rec.refresh_from_db()
        self.assertEqual(rec.status, DisposalRecommendation.Status.REJECTED)
        
        self.device.refresh_from_db()
        self.assertEqual(self.device.status, Device.Status.FOR_DISPOSAL)
