from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "full_name_display", "role", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )

    def full_name_display(self, obj):
        return obj.get_full_name()
    full_name_display.short_description = "Full Name"