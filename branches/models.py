# branches/models.py

from django.db import models
from simple_history.models import HistoricalRecords


class Branch(models.Model):
    class Grade(models.TextChoices):
        GRADE_1 = "I", "Grade I"
        GRADE_2 = "II", "Grade II"
        GRADE_3 = "III", "Grade III"
        GRADE_4 = "IV", "Grade IV"
        SPECIAL = "SPECIAL", "Special"

    name = models.CharField(max_length=255, unique=True)
    grade = models.CharField(max_length=10, choices=Grade.choices)
    employee_count = models.PositiveIntegerField()
    history = HistoricalRecords()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Branches"


class Employee(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="employees")
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"