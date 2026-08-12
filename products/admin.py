from django.contrib import admin
from .models import Category, Product, StockMovement


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_active',)


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    readonly_fields = ('movement_type', 'quantity', 'resulting_stock', 'reference', 'notes', 'created_by', 'created_at')
    can_delete = False
    max_num = 0  # prevents adding movements directly from admin — must go through adjust_stock()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sku', 'category', 'price', 'cost_price',
        'stock_quantity', 'is_low_stock_display', 'is_active',
    )
    list_filter = ('category', 'is_active', 'track_stock')
    search_fields = ('name', 'sku', 'description')
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    inlines = [StockMovementInline]

    fieldsets = (
        ('Basic Info', {'fields': ('name', 'sku', 'category', 'description')}),
        ('Pricing', {'fields': ('price', 'cost_price')}),
        ('Stock', {'fields': ('unit', 'stock_quantity', 'reorder_level', 'track_stock')}),
        ('Status', {'fields': ('is_active', 'created_by', 'created_at', 'updated_at')}),
    )

    def is_low_stock_display(self, obj):
        return obj.is_low_stock
    is_low_stock_display.short_description = 'Low Stock?'
    is_low_stock_display.boolean = True


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'resulting_stock', 'reference', 'created_by', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__name', 'product__sku', 'reference')
    readonly_fields = [f.name for f in StockMovement._meta.fields]  # fully read-only — immutable audit log

    def has_add_permission(self, request):
        return False  # movements must only be created via Product.adjust_stock()

    def has_delete_permission(self, request, obj=None):
        return False






