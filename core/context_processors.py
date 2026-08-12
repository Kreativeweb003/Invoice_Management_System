from django.utils import timezone


def sidebar_badges(request):
    """
    Injected into every template's context automatically (see settings.py
    TEMPLATES config below). Powers small notification badges in the
    navbar/sidebar — e.g. "Overdue (3)" — without every view having to
    remember to pass this data manually.

    Kept intentionally lightweight (simple .count() queries only) since
    this runs on EVERY page load, not just the dashboard.
    """
    if not request.user.is_authenticated:
        return {}

    from invoices.models import Invoice
    from products.models import Product
    from django.db.models import F

    return {
        'sidebar_overdue_count': Invoice.objects.filter(status=Invoice.Status.OVERDUE).count(),
        'sidebar_pending_count': Invoice.objects.filter(status=Invoice.Status.PENDING).count(),
        'sidebar_low_stock_count': Product.objects.filter(
            track_stock=True, is_active=True, stock_quantity__lte=F('reorder_level')
        ).count(),
        'current_year': timezone.localdate().year,
    }