# branches/models.py

from django.db import models


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

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Branches"