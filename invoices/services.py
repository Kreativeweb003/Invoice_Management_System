"""
All business logic that mutates money, stock, or invoice status lives here —
never in views or templates. Views call these functions and handle the
resulting exceptions/messages; forms only validate shape/presence of input.
"""

from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from products.models import StockMovement


TWO_PLACES = Decimal('0.01')


def _round(value):
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Totals calculation
# ---------------------------------------------------------------------------

def recalculate_invoice_totals(invoice, save=True):
    """
    The single source of truth for invoice financial totals. Recomputes:
        subtotal -> discount_amount -> tax_amount -> total_amount -> balance_due

    Always call this after items are added/edited/removed, and NEVER accept
    total_amount directly from a form submission.
    """
    from .models import Invoice

    items = invoice.items.all()
    subtotal = sum((item.line_total for item in items), Decimal('0.00'))
    subtotal = _round(subtotal)

    # --- Discount ---
    if invoice.discount_type == Invoice.DiscountType.PERCENTAGE:
        discount_amount = _round(subtotal * (invoice.discount_value / Decimal('100')))
    elif invoice.discount_type == Invoice.DiscountType.FIXED:
        discount_amount = _round(min(invoice.discount_value, subtotal))  # can't discount more than subtotal
    else:
        discount_amount = Decimal('0.00')

    taxable_amount = subtotal - discount_amount

    # --- Tax (applied after discount) ---
    tax_amount = _round(taxable_amount * (invoice.tax_percentage / Decimal('100')))

    total_amount = _round(taxable_amount + tax_amount)

    invoice.subtotal = subtotal
    invoice.discount_amount = discount_amount
    invoice.tax_amount = tax_amount
    invoice.total_amount = total_amount
    invoice.balance_due = _round(total_amount - invoice.amount_paid)

    if save:
        invoice.save(update_fields=[
            'subtotal', 'discount_amount', 'tax_amount',
            'total_amount', 'balance_due', 'updated_at'
        ])

    return invoice


# ---------------------------------------------------------------------------
# Invoice creation (with items) — used by the CreateView
# ---------------------------------------------------------------------------

@transaction.atomic
def create_invoice_with_items(invoice, item_data_list, user):
    """
    invoice: an unsaved Invoice instance (from ModelForm.save(commit=False))
    item_data_list: list of dicts: [{'product': Product, 'quantity': Decimal}, ...]
        OR [{'product': None, 'product_name': str, 'unit_price': Decimal, 'quantity': Decimal}]
        for manually-entered / non-catalog line items.
    user: the staff user creating the invoice.

    Handles:
      - invoice number assignment (locked to avoid race conditions)
      - price snapshotting from Product
      - stock sufficiency validation BEFORE committing anything
      - totals calculation
      - stock deduction (via products.Product.adjust_stock)
    """
    from .models import InvoiceItem
    from .utils import generate_invoice_number

    if not item_data_list:
        raise ValidationError("An invoice must have at least one item.")

    # --- Pre-validate stock for every catalog item before writing anything ---
    for row in item_data_list:
        product = row.get('product')
        quantity = row['quantity']
        if product is not None and not product.has_sufficient_stock(quantity):
            raise ValidationError(
                f"Insufficient stock for '{product.name}'. "
                f"Available: {product.stock_quantity}, requested: {quantity}."
            )

    invoice.invoice_number = generate_invoice_number()
    invoice.created_by = user
    invoice.full_clean(exclude=['invoice_number'])  # runs Invoice.clean()
    invoice.save()

    for row in item_data_list:
        product = row.get('product')
        quantity = row['quantity']

        if product is not None:
            item = InvoiceItem(
                invoice=invoice,
                product=product,
                product_name=product.name,
                product_sku=product.sku,
                unit_price=product.price,   # <-- snapshot taken HERE, at creation time
                quantity=quantity,
            )
        else:
            # Manually entered line item (e.g. a service/custom charge not in the catalog)
            item = InvoiceItem(
                invoice=invoice,
                product=None,
                product_name=row['product_name'],
                unit_price=row['unit_price'],
                quantity=quantity,
            )
        item.save()

    recalculate_invoice_totals(invoice)
    deduct_stock_for_invoice(invoice, user)

    return invoice


def deduct_stock_for_invoice(invoice, user):
    """Deducts stock for every catalog-linked item, once. Idempotent via
    the stock_deducted flag so re-saving an invoice never double-deducts."""
    if invoice.stock_deducted:
        return

    for item in invoice.items.select_related('product'):
        if item.product is not None and item.product.track_stock:
            item.product.adjust_stock(
                quantity=item.quantity,
                movement_type=StockMovement.MovementType.SALE,
                reference=invoice.invoice_number,
                user=user,
                notes=f"Sold via invoice {invoice.invoice_number}",
            )

    invoice.stock_deducted = True
    invoice.save(update_fields=['stock_deducted', 'updated_at'])


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

@transaction.atomic
def cancel_invoice(invoice, user, reason=''):
    """
    Cancels an invoice WITHOUT deleting it (transaction history must be
    preserved). Reverses stock deduction if it had occurred. Does NOT
    reverse recorded payments — those remain as a financial record; refunds,
    if any, should be handled as a separate manual process/note.
    """
    from .models import Invoice

    if invoice.status == Invoice.Status.CANCELLED:
        raise ValidationError("This invoice is already cancelled.")

    if invoice.stock_deducted:
        for item in invoice.items.select_related('product'):
            if item.product is not None and item.product.track_stock:
                item.product.adjust_stock(
                    quantity=item.quantity,
                    movement_type=StockMovement.MovementType.RETURN,
                    reference=invoice.invoice_number,
                    user=user,
                    notes=f"Stock reversed — invoice {invoice.invoice_number} cancelled.",
                )
        invoice.stock_deducted = False

    invoice.status = Invoice.Status.CANCELLED
    invoice.cancelled_at = timezone.now()
    invoice.cancelled_by = user
    invoice.cancellation_reason = reason
    invoice.save(update_fields=[
        'status', 'cancelled_at', 'cancelled_by',
        'cancellation_reason', 'stock_deducted', 'updated_at'
    ])
    return invoice


# ---------------------------------------------------------------------------
# Payment status synchronization — called by the payments app
# ---------------------------------------------------------------------------

def sync_invoice_payment_status(invoice):
    """
    Recomputes amount_paid/balance_due from the invoice's related Payment
    records (payments app, related_name='payments') and updates status
    accordingly. Called by payments.services after any payment is
    created/voided.

    Status logic:
      - CANCELLED invoices are never auto-transitioned.
      - amount_paid >= total_amount -> PAID
      - 0 < amount_paid < total_amount -> PARTIALLY_PAID
      - amount_paid == 0 and past due_date -> OVERDUE
      - amount_paid == 0 and not past due -> PENDING
    """
    from .models import Invoice

    if invoice.status == Invoice.Status.CANCELLED:
        return invoice

    total_paid = invoice.payments.filter(is_voided=False).aggregate(
        total=__import__('django.db.models', fromlist=['Sum']).Sum('amount')
    )['total'] or Decimal('0.00')

    invoice.amount_paid = _round(total_paid)
    invoice.balance_due = _round(invoice.total_amount - invoice.amount_paid)

    if invoice.balance_due <= Decimal('0.00'):
        invoice.status = Invoice.Status.PAID
        invoice.balance_due = Decimal('0.00')
    elif invoice.amount_paid > Decimal('0.00'):
        invoice.status = Invoice.Status.PARTIALLY_PAID
    elif invoice.is_overdue:
        invoice.status = Invoice.Status.OVERDUE
    else:
        invoice.status = Invoice.Status.PENDING

    invoice.save(update_fields=['amount_paid', 'balance_due', 'status', 'updated_at'])
    return invoice


def mark_overdue_invoices():
    """
    Batch job: flips PENDING/PARTIALLY_PAID invoices past their due_date to
    OVERDUE. Intended to be run daily via a management command / cron
    (see invoices/management/commands/update_overdue_invoices.py).
    """
    from .models import Invoice

    candidates = Invoice.objects.filter(
        status__in=[Invoice.Status.PENDING, Invoice.Status.PARTIALLY_PAID],
        due_date__lt=timezone.localdate(),
    )
    updated = candidates.update(status=Invoice.Status.OVERDUE)
    return updated



