"""
All payment business logic lives here — never trust amount/validity from
raw request data in the view. This is the enforcement point for:

    "Payment cannot exceed the outstanding balance."

After every payment create/void, invoices.services.sync_invoice_payment_status()
is called to keep Invoice.amount_paid / balance_due / status accurate.
"""

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from invoices.models import Invoice
from invoices.services import sync_invoice_payment_status
from .models import Payment


@transaction.atomic
def record_payment(invoice, amount, method, user, payment_date=None,
                    reference_number='', notes=''):
    """
    Creates a Payment against an invoice, enforcing:
      - invoice must not be CANCELLED
      - amount must be > 0
      - amount must not exceed invoice.balance_due

    Uses select_for_update to lock the invoice row for the duration of the
    transaction, preventing a race condition where two simultaneous partial
    payments could both pass the balance check and together overpay the
    invoice.
    """
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)

    if invoice.status == Invoice.Status.CANCELLED:
        raise ValidationError("Cannot record a payment against a cancelled invoice.")

    if amount is None or amount <= Decimal('0.00'):
        raise ValidationError("Payment amount must be greater than zero.")

    if amount > invoice.balance_due:
        raise ValidationError(
            f"Payment amount ({amount}) exceeds the outstanding balance "
            f"({invoice.balance_due}) for invoice {invoice.invoice_number}."
        )

    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        method=method,
        payment_date=payment_date or timezone.localdate(),
        reference_number=reference_number,
        notes=notes,
        received_by=user,
    )

    sync_invoice_payment_status(invoice)
    return payment


@transaction.atomic
def void_payment(payment, user, reason):
    """
    Voids a payment instead of deleting it — preserves the financial audit
    trail. After voiding, the invoice's amount_paid/balance_due/status are
    recalculated (the voided payment is excluded from the sum, per
    sync_invoice_payment_status filtering on is_voided=False).
    """
    if payment.is_voided:
        raise ValidationError("This payment has already been voided.")

    if not reason or not reason.strip():
        raise ValidationError("A reason is required to void a payment.")

    payment.is_voided = True
    payment.voided_at = timezone.now()
    payment.voided_by = user
    payment.void_reason = reason
    payment.save(update_fields=['is_voided', 'voided_at', 'voided_by', 'void_reason', 'updated_at'])

    sync_invoice_payment_status(payment.invoice)
    return payment



