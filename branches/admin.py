# branches/admin.py

from django.contrib import admin
from .models import Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "grade", "employee_count")
    search_fields = ("name",)