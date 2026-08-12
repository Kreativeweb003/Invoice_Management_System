from django.db import transaction
from django.utils import timezone


def generate_invoice_number():
    """
    Generates a sequential, year-scoped invoice number: INV-2026-00001.
    Wrapped in select_for_update inside a transaction by the caller
    (see services.create_invoice) to prevent race conditions under
    concurrent invoice creation.
    """
    from .models import Invoice

    year = timezone.localdate().year
    prefix = f"INV-{year}-"

    last_invoice = (
        Invoice.objects.select_for_update()
        .filter(invoice_number__startswith=prefix)
        .order_by('-invoice_number')
        .first()
    )

    if last_invoice:
        last_seq = int(last_invoice.invoice_number.split('-')[-1])
        next_seq = last_seq + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:05d}"


