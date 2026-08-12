from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from customers.models import Customer
from products.models import Product


class Invoice(models.Model):
    """
    Central invoice record. Supports two customer modes:

      - REGISTERED: `customer` FK is set, points to an existing Customer.
      - WALK_IN: `customer` is left null; `walk_in_customer_name` is used
        instead (defaults to "Walk-in Customer" if left blank).

    All monetary totals (subtotal, discount_amount, tax_amount, total_amount)
    are SERVER-COMPUTED via invoices.services.recalculate_invoice_totals().
    Never trust a total submitted directly from a form/AJAX call.
    """

    class CustomerType(models.TextChoices):
        REGISTERED = 'REGISTERED', 'Registered Customer'
        WALK_IN = 'WALK_IN', 'Walk-in Customer'

    class DiscountType(models.TextChoices):
        NONE = 'NONE', 'No Discount'
        PERCENTAGE = 'PERCENTAGE', 'Percentage (%)'
        FIXED = 'FIXED', 'Fixed Amount'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
        PAID = 'PAID', 'Paid'
        OVERDUE = 'OVERDUE', 'Overdue'
        CANCELLED = 'CANCELLED', 'Cancelled'

    # --- Identity ---
    invoice_number = models.CharField(max_length=30, unique=True, editable=False)

    # --- Customer (registered OR walk-in — see clean()) ---
    customer_type = models.CharField(
        max_length=10, choices=CustomerType.choices, default=CustomerType.WALK_IN
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.PROTECT, null=True, blank=True,
        related_name='invoices',
        help_text="Required only if customer_type is REGISTERED."
    )
    walk_in_customer_name = models.CharField(
        max_length=150, blank=True,
        help_text="Used when customer_type is WALK_IN. Defaults to 'Walk-in Customer'."
    )
    walk_in_customer_phone = models.CharField(max_length=20, blank=True)

    # --- Dates ---
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)

    # --- Financials (all server-computed — see services.py) ---
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    discount_type = models.CharField(
        max_length=10, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount_value = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0)],
        help_text="Raw input: a percentage (0-100) or a fixed amount, depending on discount_type."
    )
    discount_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text="Computed actual discount deducted from subtotal."
    )

    tax_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    tax_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    # --- Payment tracking (cached — kept in sync by payments app via services) ---
    amount_paid = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    balance_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # --- Stock integration ---
    stock_deducted = models.BooleanField(
        default=False,
        help_text="True once stock has been deducted for this invoice's items. "
                   "Prevents double-deduction and tells cancel logic whether to reverse stock."
    )

    # --- Meta ---
    notes = models.TextField(blank=True, help_text="Shown on the printed invoice/receipt.")
    internal_notes = models.TextField(blank=True, help_text="Staff-only, never printed.")

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoices_cancelled'
    )
    cancellation_reason = models.CharField(max_length=255, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoices_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['status']),
            models.Index(fields=['issue_date']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.customer_display_name}"

    def get_absolute_url(self):
        return reverse('invoices:invoice_detail', kwargs={'pk': self.pk})

    # -----------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------

    def clean(self):
        errors = {}

        if self.customer_type == self.CustomerType.REGISTERED and not self.customer_id:
            errors['customer'] = "A registered customer must be selected when customer type is 'Registered'."

        if self.customer_type == self.CustomerType.WALK_IN and self.customer_id:
            errors['customer'] = "Walk-in invoices should not have a registered customer attached."

        if self.discount_type == self.DiscountType.PERCENTAGE and self.discount_value > 100:
            errors['discount_value'] = "Percentage discount cannot exceed 100%."

        if errors:
            raise ValidationError(errors)

    # -----------------------------------------------------------------
    # Display helpers (used in templates, PDFs, receipts)
    # -----------------------------------------------------------------

    @property
    def customer_display_name(self):
        if self.customer_type == self.CustomerType.REGISTERED and self.customer:
            return self.customer.display_name
        return self.walk_in_customer_name.strip() or "Walk-in Customer"

    @property
    def customer_display_phone(self):
        if self.customer_type == self.CustomerType.REGISTERED and self.customer:
            return self.customer.phone_number
        return self.walk_in_customer_phone

    @property
    def customer_display_address(self):
        if self.customer_type == self.CustomerType.REGISTERED and self.customer:
            parts = [self.customer.address_line, self.customer.city, self.customer.state, self.customer.country]
            return ", ".join(p for p in parts if p)
        return ""

    @property
    def is_editable(self):
        """Cancelled or fully paid invoices should not have items edited."""
        return self.status not in [self.Status.CANCELLED, self.Status.PAID]

    @property
    def is_overdue(self):
        return (
            self.status in [self.Status.PENDING, self.Status.PARTIALLY_PAID]
            and self.due_date is not None
            and self.due_date < timezone.localdate()
        )

    @property
    def item_count(self):
        return self.items.count()


class InvoiceItem(models.Model):
    """
    A single line item on an invoice.

    CRITICAL: `unit_price` and `product_name` are SNAPSHOTS taken at the
    moment this item is created — they are copied from Product and then
    never touched again, even if Product.price or Product.name changes
    later. This is what guarantees historical invoice accuracy.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')

    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invoice_items',
        help_text="Link to the live product. May become null if the product is later deleted, "
                   "but product_name/unit_price below preserve the historical record regardless."
    )
    product_name = models.CharField(
        max_length=200,
        help_text="Snapshot of the product name at time of sale."
    )
    product_sku = models.CharField(max_length=50, blank=True)

    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Snapshot of the product's price at time of sale. Never recalculated from Product.price."
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    line_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        help_text="Computed as unit_price * quantity. Set automatically on save()."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"

    def save(self, *args, **kwargs):
        self.line_total = (self.unit_price * self.quantity).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)





