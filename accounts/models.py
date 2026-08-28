from django.db import models

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        IT_STAFF = "IT_STAFF", "IT Support Staff"
        MANAGER = "MANAGER", "District Manager"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.IT_STAFF,
    )

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
    