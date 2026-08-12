from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import CustomUser


class LoginForm(AuthenticationForm):
    """Login form. Widget styling attrs included so templates can be built later
    without needing to touch this form again."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
        })
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if getattr(user, 'is_disabled', False):
            raise ValidationError(
                "This account has been disabled. Contact an administrator.",
                code='disabled',
            )


class StaffCreationForm(UserCreationForm):
    """Used by Admins to create new staff/manager/cashier accounts."""

    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True, max_length=150)
    last_name = forms.CharField(required=True, max_length=150)

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'phone_number', 'role', 'password1', 'password2',
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email


class StaffUpdateForm(UserChangeForm):
    """Used by Admins to edit an existing staff account. Excludes password
    (handled via a separate password-reset flow)."""

    password = None  # remove the password field/hash display inherited from UserChangeForm

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'phone_number', 'role', 'is_active', 'is_disabled',
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A user with this email already exists.")
        return email


class ProfileUpdateForm(forms.ModelForm):
    """Used by any logged-in user to edit their own basic info.
    Deliberately excludes role/is_active/is_disabled — those are admin-only."""

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone_number']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        qs = CustomUser.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A user with this email already exists.")
        return email