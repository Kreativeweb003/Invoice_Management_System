from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator


class CustomUser(AbstractUser):
    """
    Custom user model supporting role-based access control.

    Roles:
        ADMIN   - Full system access (manage users, products, customers,
                  invoices, payments, reports, settings).
        MANAGER - Manage products, customers, invoices, payments, reports.
                  Cannot manage user accounts.
        CASHIER - Create invoices, record payments, view products/customers.
                  Cannot edit products, delete records, or view financial reports.
    """

    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        MANAGER = 'MANAGER', 'Manager'
        CASHIER = 'CASHIER', 'Cashier'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CASHIER,
        help_text="Determines what parts of the system this user can access."
    )

    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True
    )

    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users',
        help_text="The admin who created this staff account."
    )

    is_disabled = models.BooleanField(
        default=False,
        help_text="If true, user cannot log in even though is_active may be True. "
                   "Used for soft-disabling staff accounts instead of deleting them."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_joined']
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER

    @property
    def is_cashier(self):
        return self.role == self.Role.CASHIER

    def can_manage_users(self):
        return self.is_admin

    def can_manage_products(self):
        return self.is_admin or self.is_manager

    def can_view_reports(self):
        return self.is_admin or self.is_manager

    def can_cancel_invoice(self):
        return self.is_admin or self.is_manager