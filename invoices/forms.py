from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet, formset_factory

from customers.models import Customer
from products.models import Product
from .models import Invoice


class InvoiceForm(forms.ModelForm):
    """
    Header-level invoice form. Item lines are handled separately via
    InvoiceItemFormSet (formset_factory below), NOT as a ModelForm/
    inlineformset, because on create the Invoice doesn't exist yet —
    services.create_invoice_with_items() creates the Invoice and items
    together in one atomic transaction.
    """

    class Meta:
        model = Invoice
        fields = [
            'customer_type', 'customer', 'walk_in_customer_name', 'walk_in_customer_phone',
            'issue_date', 'due_date',
            'discount_type', 'discount_value', 'tax_percentage',
            'notes', 'internal_notes',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'internal_notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['customer'].required = False
        self.fields['walk_in_customer_name'].required = False

    def clean(self):
        cleaned_data = super().clean()
        customer_type = cleaned_data.get('customer_type')
        customer = cleaned_data.get('customer')
        walk_in_name = cleaned_data.get('walk_in_customer_name')

        if customer_type == Invoice.CustomerType.REGISTERED:
            if not customer:
                self.add_error('customer', "Please select a registered customer.")
            # Clear walk-in fields to keep data clean
            cleaned_data['walk_in_customer_name'] = ''
            cleaned_data['walk_in_customer_phone'] = cleaned_data.get('walk_in_customer_phone') or ''
        else:  # WALK_IN
            cleaned_data['customer'] = None
            if not walk_in_name:
                cleaned_data['walk_in_customer_name'] = "Walk-in Customer"

        discount_type = cleaned_data.get('discount_type')
        discount_value = cleaned_data.get('discount_value') or Decimal('0.00')
        if discount_type == Invoice.DiscountType.PERCENTAGE and discount_value > 100:
            self.add_error('discount_value', "Percentage discount cannot exceed 100%.")
        if discount_value < 0:
            self.add_error('discount_value', "Discount cannot be negative.")

        due_date = cleaned_data.get('due_date')
        issue_date = cleaned_data.get('issue_date')
        if due_date and issue_date and due_date < issue_date:
            self.add_error('due_date', "Due date cannot be before the issue date.")

        return cleaned_data


class InvoiceItemLineForm(forms.Form):
    """
    A single line item row, used inside InvoiceItemFormSet. Deliberately a
    plain Form (not ModelForm) since items are persisted only through
    services.create_invoice_with_items(), after the parent Invoice exists.

    Two ways to fill a line:
      1. Pick `product` -> product_name/unit_price are auto-filled server-side
         from the live Product record at submit time.
      2. Leave `product` blank and fill `product_name` + `unit_price` manually
         -> for one-off/custom/service charges not in the catalog.
    """
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True), required=False
    )
    product_name = forms.CharField(max_length=200, required=False)
    unit_price = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False, min_value=Decimal('0.00')
    )
    quantity = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01')
    )

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        product_name = cleaned_data.get('product_name')
        unit_price = cleaned_data.get('unit_price')
        quantity = cleaned_data.get('quantity')

        if not product and not product_name:
            raise ValidationError("Select a product or enter a custom item name.")

        if not product:
            if unit_price is None:
                self.add_error('unit_price', "Unit price is required for a custom item.")

        if product and quantity and not product.has_sufficient_stock(quantity):
            raise ValidationError(
                f"Insufficient stock for '{product.name}'. "
                f"Available: {product.stock_quantity}, requested: {quantity}."
            )

        return cleaned_data

    def to_item_data(self):
        """Converts validated form data into the dict shape services.create_invoice_with_items expects."""
        product = self.cleaned_data.get('product')
        if product:
            return {'product': product, 'quantity': self.cleaned_data['quantity']}
        return {
            'product': None,
            'product_name': self.cleaned_data['product_name'],
            'unit_price': self.cleaned_data['unit_price'],
            'quantity': self.cleaned_data['quantity'],
        }


class BaseInvoiceItemFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return
        non_empty_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
        if not non_empty_forms:
            raise ValidationError("An invoice must contain at least one item.")


InvoiceItemFormSet = formset_factory(
    InvoiceItemLineForm,
    formset=BaseInvoiceItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class InvoiceCancelForm(forms.Form):
    reason = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={'rows': 2}),
        required=True,
        label="Reason for cancellation",
    )


class InvoiceSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (invoice #, customer)")
    status = forms.ChoiceField(
        required=False, choices=[('', 'All')] + list(Invoice.Status.choices)
    )
    customer_type = forms.ChoiceField(
        required=False, choices=[('', 'All')] + list(Invoice.CustomerType.choices)
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))




