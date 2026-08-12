from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'company_name', 'phone_number', 'email',
        'is_active', 'invoice_count_display', 'created_at',
    )
    list_filter = ('is_active', 'city', 'country')
    search_fields = ('full_name', 'company_name', 'phone_number', 'email')
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    ordering = ('full_name',)

    fieldsets = (
        ('Identity', {'fields': ('full_name', 'company_name')}),
        ('Contact', {'fields': ('phone_number', 'email')}),
        ('Address', {'fields': ('address_line', 'city', 'state', 'country')}),
        ('Meta', {'fields': ('notes', 'is_active', 'created_by', 'created_at', 'updated_at')}),
    )

    def invoice_count_display(self, obj):
        return obj.invoice_count
    invoice_count_display.short_description = 'Invoices'