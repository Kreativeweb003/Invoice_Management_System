from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_number', 'invoice', 'amount', 'method',
        'payment_date', 'is_voided', 'received_by', 'created_at',
    )
    list_filter = ('method', 'is_voided', 'payment_date')
    search_fields = ('payment_number', 'invoice__invoice_number', 'reference_number')
    readonly_fields = (
        'payment_number', 'invoice', 'amount', 'method', 'payment_date',
        'reference_number', 'received_by', 'created_at', 'updated_at',
        'voided_at', 'voided_by',
    )

    fieldsets = (
        ('Payment', {'fields': (
            'payment_number', 'invoice', 'amount', 'method',
            'payment_date', 'reference_number', 'notes', 'received_by',
        )}),
        ('Void Status', {'fields': ('is_voided', 'voided_at', 'voided_by', 'void_reason')}),
        ('Meta', {'fields': ('created_at', 'updated_at')}),
    )

    def has_add_permission(self, request):
        return False  # payments must go through services.record_payment() to enforce balance rules

    def has_delete_permission(self, request, obj=None):
        return False  # void, never delete — preserves financial audit trail

    def save_model(self, request, obj, form, change):
        """
        Even though add is disabled, guard the void-toggle path here too:
        if staff flip is_voided=True directly in admin, route it through
        the service so sync_invoice_payment_status() still fires correctly.
        """
        if change and 'is_voided' in form.changed_data and obj.is_voided:
            from . import services
            services.void_payment(obj, request.user, obj.void_reason or "Voided via admin.")
        else:
            super().save_model(request, obj, form, change)






  