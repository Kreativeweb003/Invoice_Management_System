from django.contrib import admin
from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ('product_name', 'product_sku', 'unit_price', 'quantity', 'line_total')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # items must go through services.create_invoice_with_items()


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        'invoice_number', 'customer_display_name', 'customer_type',
        'total_amount', 'amount_paid', 'balance_due', 'status', 'issue_date', 'due_date',
    )
    list_filter = ('status', 'customer_type', 'issue_date')
    search_fields = ('invoice_number', 'customer__full_name', 'walk_in_customer_name')
    readonly_fields = (
        'invoice_number', 'subtotal', 'discount_amount', 'tax_amount', 'total_amount',
        'amount_paid', 'balance_due', 'stock_deducted',
        'cancelled_at', 'cancelled_by', 'created_by', 'created_at', 'updated_at',
    )
    inlines = [InvoiceItemInline]

    fieldsets = (
        ('Identity', {'fields': ('invoice_number', 'status')}),
        ('Customer', {'fields': (
            'customer_type', 'customer', 'walk_in_customer_name', 'walk_in_customer_phone'
        )}),
        ('Dates', {'fields': ('issue_date', 'due_date')}),
        ('Financials', {'fields': (
            'discount_type', 'discount_value', 'discount_amount',
            'tax_percentage', 'tax_amount', 'subtotal', 'total_amount',
            'amount_paid', 'balance_due',
        )}),
        ('Notes', {'fields': ('notes', 'internal_notes')}),
        ('Cancellation', {'fields': ('cancelled_at', 'cancelled_by', 'cancellation_reason')}),
        ('Meta', {'fields': ('stock_deducted', 'created_by', 'created_at', 'updated_at')}),
    )

    def has_delete_permission(self, request, obj=None):
        return False  # cancelled invoices stay in the system — never hard-deleted







