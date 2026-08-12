from decimal import Decimal
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone

from invoices.models import Invoice


class Payment(models.Model):
    """
    A single payment against an invoice. One invoice can have many payments
    (partial payments over time, or one full payment).

    Payments are NEVER hard-deleted — if a payment was recorded in error,
    it is VOIDED instead (is_voided=True), which preserves the audit trail
    while excluding it from amount_paid calculations going forward.
    """

    class Method(models.TextChoices):
        CASH = 'CASH', 'Cash'
        CARD = 'CARD', 'Credit/Debit Card'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        MOBILE_MONEY = 'MOBILE_MONEY', 'Mobile Money'
        CHEQUE = 'CHEQUE', 'Cheque'
        OTHER = 'OTHER', 'Other'

    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name='payments'
    )

    payment_number = models.CharField(max_length=30, unique=True, editable=False)

    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Must not exceed the invoice's outstanding balance at the time of payment."
    )
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    reference_number = models.CharField(
        max_length=100, blank=True,
        help_text="Transaction ID, cheque number, mobile money reference, etc."
    )
    payment_date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    # --- Void handling (soft-delete equivalent) ---
    is_voided = models.BooleanField(default=False)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments_voided'
    )
    void_reason = models.CharField(max_length=255, blank=True)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='payments_received'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['invoice', 'is_voided']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['payment_number']),
        ]

    def __str__(self):
        status = " (VOIDED)" if self.is_voided else ""
        return f"{self.payment_number} - {self.invoice.invoice_number} - {self.amount}{status}"

    def save(self, *args, **kwargs):
        if not self.payment_number:
            self.payment_number = self._generate_payment_number()
        super().save(*args, **kwargs)

    def _generate_payment_number(self):
        """Sequential, year-scoped: PMT-2026-00001. Generation itself is
        locked via select_for_update in services.record_payment to avoid
        race conditions under concurrent payment creation."""
        year = timezone.localdate().year
        prefix = f"PMT-{year}-"
        last = Payment.objects.filter(payment_number__startswith=prefix).order_by('-payment_number').first()
        next_seq = (int(last.payment_number.split('-')[-1]) + 1) if last else 1
        return f"{prefix}{next_seq:05d}"




