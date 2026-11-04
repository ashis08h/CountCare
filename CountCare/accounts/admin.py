
from django.contrib import admin
from .models import Company, CompanyEmployee, Role, Permission


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "gst_number", "email", "is_active", "created_at")
    search_fields = ("name", "gst_number", "email")
    list_filter = ("is_active",)


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("module", "action", "codename", "description")
    list_filter = ("module", "action")
    search_fields = ("codename", "description")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "is_system_role", "created_at")
    list_filter = ("company", "is_system_role")
    search_fields = ("name", "company__name")
    filter_horizontal = ("permissions",)


@admin.register(CompanyEmployee)
class CompanyEmployeeAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "is_active", "joined_at")
    list_filter = ("company", "role", "is_active")
    search_fields = ("user__username", "user__email", "company__name")
