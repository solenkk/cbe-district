from django import forms
from django.core.exceptions import ValidationError


class ReportPeriodForm(forms.Form):
    period_start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("period_start")
        end = cleaned_data.get("period_end")

        if start and end and start > end:
            raise ValidationError("Period start date cannot be after period end date.")
        return cleaned_data