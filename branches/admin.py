# branches/admin.py

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Branch, Employee


@admin.register(Branch)
class BranchAdmin(SimpleHistoryAdmin):
    list_display = ("name", "grade", "employee_count")
    search_fields = ("name",)


@admin.register(Employee)
class EmployeeAdmin(SimpleHistoryAdmin):
    list_display = ("first_name", "last_name", "department", "branch")
    search_fields = ("first_name", "last_name", "department")
    list_filter = ("branch",)