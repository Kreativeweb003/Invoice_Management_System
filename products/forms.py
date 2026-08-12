from django import forms
from django.core.exceptions import ValidationError
from .models import Product, Category, StockMovement


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'is_active']


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'sku', 'category', 'description',
            'price', 'cost_price', 'unit',
            'stock_quantity', 'reorder_level', 'track_stock', 'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        help_texts = {
            'sku': 'Leave blank to auto-generate.',
        }

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError("Price cannot be negative.")
        return price

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            qs = Product.objects.filter(sku__iexact=sku)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("A product with this SKU already exists.")
        return sku

    def clean(self):
        cleaned_data = super().clean()
        cost_price = cleaned_data.get('cost_price')
        price = cleaned_data.get('price')
        if cost_price is not None and price is not None and cost_price > price:
            self.add_error(
                'cost_price',
                "Cost price is higher than selling price — this product would sell at a loss."
            )
        return cleaned_data

    def clean_stock_quantity(self):
        """
        On CREATE, this field sets the opening stock directly.
        On UPDATE, direct edits here bypass the StockMovement audit trail,
        so the view will redirect stock corrections through the dedicated
        StockAdjustmentForm instead (see below) rather than allowing silent
        edits through this form for existing products.
        """
        qty = self.cleaned_data.get('stock_quantity')
        if qty is not None and qty < 0:
            raise ValidationError("Stock quantity cannot be negative.")
        return qty


class StockAdjustmentForm(forms.Form):
    """
    The ONLY sanctioned way to change stock on an existing product outside
    of a sale. Routes through Product.adjust_stock() so every change is
    logged in StockMovement.
    """

    ADJUSTMENT_CHOICES = (
        (StockMovement.MovementType.PURCHASE, 'Stock Purchase / Restock'),
        (StockMovement.MovementType.RETURN, 'Customer Return'),
        (StockMovement.MovementType.ADJUSTMENT_IN, 'Manual Adjustment (Increase)'),
        (StockMovement.MovementType.ADJUSTMENT_OUT, 'Manual Adjustment (Decrease)'),
        (StockMovement.MovementType.DAMAGED, 'Damaged / Written Off'),
    )

    movement_type = forms.ChoiceField(choices=ADJUSTMENT_CHOICES)
    quantity = forms.DecimalField(min_value=0.01, max_digits=12, decimal_places=2)
    reference = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)


class ProductSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(is_active=True), required=False
    )
    stock_status = forms.ChoiceField(
        required=False,
        choices=(
            ('', 'All'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock'),
        ),
    )




