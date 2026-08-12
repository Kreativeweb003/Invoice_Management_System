from django import forms
from django.core.exceptions import ValidationError
from .models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'full_name', 'company_name', 'phone_number', 'email',
            'address_line', 'city', 'state', 'country', 'notes', 'is_active',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        phone = cleaned_data.get('phone_number')
        email = cleaned_data.get('email')

        # Business rule: contact info is optional overall, but if the
        # business does capture a customer, we recommend at least one
        # way to reach them. This is a soft validation (warning-level),
        # not a hard block, since the field itself is not required.
        if not phone and not email:
            self.add_error(
                None,
                "Consider adding a phone number or email so this customer "
                "can be contacted (not required, but recommended)."
            )
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            qs = Customer.objects.filter(email__iexact=email)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("A customer with this email already exists.")
        return email

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            qs = Customer.objects.filter(phone_number=phone)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("A customer with this phone number already exists.")
        return phone


class CustomerQuickCreateForm(forms.ModelForm):
    """
    Minimal-friction version of CustomerForm used in the AJAX quick-create
    modal during invoice creation. Only asks for what's needed to identify
    the customer later — the full profile can be filled in afterward from
    the Customers section.
    """

    class Meta:
        model = Customer
        fields = ['full_name', 'phone_number', 'email']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Customer.objects.filter(email__iexact=email).exists():
            raise ValidationError("A customer with this email already exists.")
        return email


class CustomerSearchForm(forms.Form):
    """Used to render/validate the search & filter bar on the customer list page."""
    q = forms.CharField(required=False, label="Search")
    status = forms.ChoiceField(
        required=False,
        choices=(('', 'All'), ('active', 'Active'), ('inactive', 'Inactive')),
    )