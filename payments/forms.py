from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from .models import Payment


class PaymentForm(forms.Form):
    """
    Plain Form (not ModelForm) since actual persistence + balance validation
    happens in services.record_payment() inside an atomic, row-locked
    transaction — this form only validates shape/presence of submitted data.
    The invoice itself is passed in via __init__ so we can show a live
    'max payable' hint and do a first-pass validation here too (defense in
    depth; the authoritative check still happens in the service).
    """
    amount = forms.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )
    method = forms.ChoiceField(choices=Payment.Method.choices)
    payment_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={'type': 'date'})
    )
    reference_number = forms.CharField(max_length=100, required=False)
    notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    def __init__(self, *args, invoice=None, **kwargs):
        self.invoice = invoice
        super().__init__(*args, **kwargs)
        if invoice is not None:
            self.fields['amount'].widget.attrs['max'] = str(invoice.balance_due)
            self.fields['amount'].help_text = f"Outstanding balance: {invoice.balance_due}"

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        if self.invoice and amount > self.invoice.balance_due:
            raise ValidationError(
                f"Amount cannot exceed the outstanding balance of {self.invoice.balance_due}."
            )
        return amount


class PaymentVoidForm(forms.Form):
    reason = forms.CharField(
        max_length=255,
        widget=forms.Textarea(attrs={'rows': 2}),
        label="Reason for voiding this payment",
    )


class PaymentSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (payment #, invoice #, reference)")
    method = forms.ChoiceField(
    required=False, choices=[('', 'All')] + list(Payment.Method.choices)
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    include_voided = forms.BooleanField(required=False, initial=False)




