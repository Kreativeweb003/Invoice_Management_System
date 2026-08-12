from django.db import models
from django.core.validators import RegexValidator
from django.urls import reverse
from django.conf import settings


class Customer(models.Model):
    """
    Registered customer record. Entirely optional to create — walk-in
    sales do NOT require a Customer instance. This model only exists
    for businesses that want to track repeat customers, their contact
    info, and their invoice history.
    """

    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
    )

    # --- Identity ---
    full_name = models.CharField(max_length=150)
    company_name = models.CharField(max_length=150, blank=True)

    # --- Contact (all optional — some businesses only get a phone number) ---
    phone_number = models.CharField(
        validators=[phone_regex], max_length=17, blank=True
    )
    email = models.EmailField(blank=True)

    # --- Address (optional, useful for invoices/delivery) ---
    address_line = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # --- Business meta ---
    notes = models.TextField(blank=True, help_text="Internal notes, not shown on invoices.")
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive customers are hidden from selection lists but "
                   "their invoice history is preserved."
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customers_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        if self.company_name:
            return f"{self.full_name} ({self.company_name})"
        return self.full_name

    def get_absolute_url(self):
        return reverse('customers:customer_detail', kwargs={'pk': self.pk})

    # --- Convenience properties used later by invoices/reports ---

    @property
    def display_name(self):
        """Name shown on invoices / PDF receipts."""
        return self.company_name or self.full_name

    @property
    def invoice_count(self):
        """Relies on the reverse FK 'invoices' defined on the Invoice model
        in the invoices app (invoices.Invoice.customer, related_name='invoices')."""
        return self.invoices.count()

    @property
    def total_outstanding_balance(self):
        """
        Sum of balance_due across all of this customer's non-cancelled invoices.
        Safe to call even before the invoices app exists, since it degrades
        gracefully if the related manager isn't populated yet.
        """
        from django.db.models import Sum
        aggregate = self.invoices.exclude(status='CANCELLED').aggregate(
            total=Sum('balance_due')
        )
        return aggregate['total'] or 0

    @property
    def total_spent(self):
        """Sum of total_amount across paid/partially-paid invoices."""
        from django.db.models import Sum
        aggregate = self.invoices.filter(
            status__in=['PAID', 'PARTIALLY_PAID']
        ).aggregate(total=Sum('total_amount'))
        return aggregate['total'] or 0