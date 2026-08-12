from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = (
        'username', 'email', 'first_name', 'last_name',
        'role', 'is_active', 'is_disabled', 'date_joined',
    )
    list_filter = ('role', 'is_active', 'is_disabled', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = UserAdmin.fieldsets + (
        ('Role & Contact', {
            'fields': ('role', 'phone_number', 'is_disabled', 'created_by')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Contact', {
            'fields': ('role', 'phone_number', 'email', 'first_name', 'last_name')
        }),
    )
    readonly_fields = ('created_by', 'created_at', 'updated_at')