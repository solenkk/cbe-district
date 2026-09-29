from django import forms
from .models import Device, Component
from .services import DEVICE_STATUS_TRANSITIONS


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["serial_number", "tag_number", "device_type", "model", "branch", "condition_notes"]


class StatusChangeForm(forms.Form):
    new_status = forms.ChoiceField(choices=[])
    note = forms.CharField(widget=forms.Textarea, required=False)

    def __init__(self, *args, device=None, **kwargs):
        super().__init__(*args, **kwargs)
        if device:
            allowed = DEVICE_STATUS_TRANSITIONS.get(device.status, set())
            self.fields["new_status"].choices = [(s, Device.Status(s).label) for s in allowed]
        else:
            self.fields["new_status"].choices = []


class ComponentLogForm(forms.Form):
    source_device = forms.ModelChoiceField(
        queryset=Device.objects.exclude(status=Device.Status.RETURNED_TO_BRANCH).select_related("branch").order_by("-date_received"),
        label="Source Device (Donor)",
    )
    component_type = forms.ChoiceField(
        choices=Component.ComponentType.choices,
        label="Component Type",
    )


class ComponentInstallForm(forms.Form):
    component = forms.ModelChoiceField(
        queryset=Component.objects.filter(status=Component.Status.IN_STOCK).select_related("source_device"),
        label="Select In-Stock Component",
    )
    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional installation details (e.g. upgraded slot)"}),
        required=False,
        label="Installation Note",
    )


class DisposalRecommendationForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Explain why this device should be disposed."}),
        label="Reason for Disposal",
        required=True
    )


class DisposalReviewForm(forms.Form):
    action = forms.ChoiceField(
        choices=[("APPROVE", "Approve Disposal"), ("REJECT", "Reject Disposal")],
        widget=forms.RadioSelect
    )
    note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional note..."}),
        required=False,
        label="Review Note"
    )