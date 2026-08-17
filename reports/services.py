"""
All report aggregation logic lives here — views just call these functions
and pass the results to templates or JsonResponse. Centralizing this means
the dashboard (core app) can reuse the exact same queries as the full
report pages, guaranteeing numbers always match.
"""

from decimal import Decimal
from datetime import timedelta
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone

from invoices.models import Invoice, InvoiceItem
from payments.models import Payment


ZERO = Decimal('0.00')


def _date_range_filter(queryset, date_field, date_from=None, date_to=None):
    if date_from:
        queryset = queryset.filter(**{f'{date_field}__gte': date_from})
    if date_to:
        queryset = queryset.filter(**{f'{date_field}__lte': date_to})
    return queryset


def _bucket_date(d, granularity):
    """
    Buckets a plain date into a period start-date, done entirely in Python
    to avoid relying on SQLite's TruncDate/TruncWeek/TruncMonth — which have
    a known incompatibility with Python 3.12's sqlite3 module regardless of
    Django/TIME_ZONE settings (fails with "'tzinfo' is an invalid keyword
    argument for replace()" inside Django's SQLite backend internals).
    """
    if granularity == 'week':
        return d - timedelta(days=d.weekday())  # Monday of that week
    elif granularity == 'month':
        return d.replace(day=1)
    return d  # day — no bucketing needed


# ---------------------------------------------------------------------------
# Sales report
# ---------------------------------------------------------------------------

def get_sales_summary(date_from=None, date_to=None, include_cancelled=False):
    """
    High-level KPIs for the sales report header cards:
    total invoices, total sales value, average invoice value, total items sold.
    """
    queryset = Invoice.objects.all()
    if not include_cancelled:
        queryset = queryset.exclude(status=Invoice.Status.CANCELLED)
    queryset = _date_range_filter(queryset, 'issue_date', date_from, date_to)

    summary = queryset.aggregate(
        invoice_count=Count('id'),
        total_sales=Sum('total_amount'),
        total_subtotal=Sum('subtotal'),
        total_discount=Sum('discount_amount'),
        total_tax=Sum('tax_amount'),
        average_invoice_value=Avg('total_amount'),
    )

    for key in ('total_sales', 'total_subtotal', 'total_discount', 'total_tax'):
        summary[key] = summary[key] or ZERO
    summary['average_invoice_value'] = summary['average_invoice_value'] or ZERO
    summary['invoice_count'] = summary['invoice_count'] or 0

    items_sold = InvoiceItem.objects.filter(
        invoice__in=queryset
    ).aggregate(total_quantity=Sum('quantity'))['total_quantity'] or ZERO
    summary['total_items_sold'] = items_sold

    return summary


def get_sales_by_status(date_from=None, date_to=None):
    """Breakdown of invoice count/value grouped by status — feeds a pie/bar chart."""
    queryset = Invoice.objects.all()
    queryset = _date_range_filter(queryset, 'issue_date', date_from, date_to)

    return list(
        queryset.values('status')
        .annotate(count=Count('id'), total_value=Sum('total_amount'))
        .order_by('status')
    )


def get_sales_trend(date_from=None, date_to=None, granularity='day'):
    """
    Time-series sales data for the dashboard/report line chart.
    granularity: 'day', 'week', or 'month'.

    Bucketed in Python rather than via SQLite's TruncDate/TruncWeek/TruncMonth
    — see _bucket_date() docstring for why.
    """
    queryset = Invoice.objects.exclude(status=Invoice.Status.CANCELLED)
    queryset = _date_range_filter(queryset, 'issue_date', date_from, date_to)
    rows = queryset.values('issue_date', 'total_amount')

    buckets = {}
    for row in rows:
        period = _bucket_date(row['issue_date'], granularity)
        if period not in buckets:
            buckets[period] = {'period': period, 'total_sales': ZERO, 'invoice_count': 0}
        buckets[period]['total_sales'] += row['total_amount'] or ZERO
        buckets[period]['invoice_count'] += 1

    return [buckets[key] for key in sorted(buckets.keys())]


def get_top_selling_products(date_from=None, date_to=None, limit=10):
    """
    Best sellers by quantity and revenue. Uses InvoiceItem's frozen
    product_name/unit_price snapshots, so historical accuracy is preserved
    even if a product was later renamed, repriced, or deactivated.
    """
    queryset = InvoiceItem.objects.exclude(
        invoice__status=Invoice.Status.CANCELLED
    )
    if date_from:
        queryset = queryset.filter(invoice__issue_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(invoice__issue_date__lte=date_to)

    return list(
        queryset.values('product_name')
        .annotate(
            total_quantity_sold=Sum('quantity'),
            total_revenue=Sum('line_total'),
        )
        .order_by('-total_revenue')[:limit]
    )


def get_sales_by_customer_type(date_from=None, date_to=None):
    """Registered vs Walk-in split — useful for seeing how much of the
    business comes from repeat/registered customers vs walk-ins."""
    queryset = Invoice.objects.exclude(status=Invoice.Status.CANCELLED)
    queryset = _date_range_filter(queryset, 'issue_date', date_from, date_to)

    return list(
        queryset.values('customer_type')
        .annotate(count=Count('id'), total_value=Sum('total_amount'))
        .order_by('customer_type')
    )


def get_top_customers(date_from=None, date_to=None, limit=10):
    """Highest-spending registered customers. Walk-ins are excluded since
    they have no persistent identity to aggregate against."""
    queryset = Invoice.objects.filter(
        customer_type=Invoice.CustomerType.REGISTERED
    ).exclude(status=Invoice.Status.CANCELLED)
    queryset = _date_range_filter(queryset, 'issue_date', date_from, date_to)

    return list(
        queryset.values('customer__id', 'customer__full_name', 'customer__company_name')
        .annotate(invoice_count=Count('id'), total_spent=Sum('total_amount'))
        .order_by('-total_spent')[:limit]
    )


# ---------------------------------------------------------------------------
# Payment report
# ---------------------------------------------------------------------------

def get_payment_summary(date_from=None, date_to=None):
    """KPI cards for the payments report: total collected, payment count, average payment."""
    queryset = Payment.objects.filter(is_voided=False)
    queryset = _date_range_filter(queryset, 'payment_date', date_from, date_to)

    summary = queryset.aggregate(
        total_collected=Sum('amount'),
        payment_count=Count('id'),
        average_payment=Avg('amount'),
    )
    summary['total_collected'] = summary['total_collected'] or ZERO
    summary['average_payment'] = summary['average_payment'] or ZERO
    summary['payment_count'] = summary['payment_count'] or 0

    voided_count = Payment.objects.filter(is_voided=True)
    voided_count = _date_range_filter(voided_count, 'payment_date', date_from, date_to).count()
    summary['voided_count'] = voided_count

    return summary


def get_payments_by_method(date_from=None, date_to=None):
    """Breakdown by payment method — feeds a pie chart (cash vs card vs transfer, etc.)."""
    queryset = Payment.objects.filter(is_voided=False)
    queryset = _date_range_filter(queryset, 'payment_date', date_from, date_to)

    return list(
        queryset.values('method')
        .annotate(count=Count('id'), total_amount=Sum('amount'))
        .order_by('-total_amount')
    )


def get_payment_trend(date_from=None, date_to=None, granularity='day'):
    """Time-series of collections — feeds the payments report line chart.
    Bucketed in Python — see _bucket_date() docstring for why."""
    queryset = Payment.objects.filter(is_voided=False)
    queryset = _date_range_filter(queryset, 'payment_date', date_from, date_to)
    rows = queryset.values('payment_date', 'amount')

    buckets = {}
    for row in rows:
        period = _bucket_date(row['payment_date'], granularity)
        if period not in buckets:
            buckets[period] = {'period': period, 'total_collected': ZERO, 'payment_count': 0}
        buckets[period]['total_collected'] += row['amount'] or ZERO
        buckets[period]['payment_count'] += 1

    return [buckets[key] for key in sorted(buckets.keys())]


def get_daily_collections_by_staff(date_from=None, date_to=None):
    """
    Cash reconciliation helper: how much each staff member collected in the
    period, broken down by method. Useful for end-of-shift/day cash-ups.
    """
    queryset = Payment.objects.filter(is_voided=False)
    queryset = _date_range_filter(queryset, 'payment_date', date_from, date_to)

    return list(
        queryset.values('received_by__id', 'received_by__username', 'method')
        .annotate(total_amount=Sum('amount'), count=Count('id'))
        .order_by('received_by__username', 'method')
    )


# ---------------------------------------------------------------------------
# Outstanding balance report
# ---------------------------------------------------------------------------

def get_outstanding_invoices(date_from=None, date_to=None, only_overdue=False):
    """
    All invoices with a balance still owed. Excludes CANCELLED (they carry
    no real obligation) and PAID (nothing owed) automatically via the
    balance_due__gt=0 filter, since sync_invoice_payment_status() zeroes
    balance_due once fully paid.
    """
    queryset = Invoice.objects.filter(
        balance_due__gt=ZERO
    ).exclude(status=Invoice.Status.CANCELLED).select_related('customer')

    queryset = _date_range_filter(queryset, 'issue_date', date_from, date_to)

    if only_overdue:
        queryset = queryset.filter(status=Invoice.Status.OVERDUE)

    return queryset.order_by('due_date', 'issue_date')


def get_outstanding_summary(date_from=None, date_to=None):
    """KPI cards for the outstanding balance report."""
    queryset = get_outstanding_invoices(date_from, date_to)

    summary = queryset.aggregate(
        total_outstanding=Sum('balance_due'),
        invoice_count=Count('id'),
    )
    summary['total_outstanding'] = summary['total_outstanding'] or ZERO
    summary['invoice_count'] = summary['invoice_count'] or 0

    summary['overdue_count'] = queryset.filter(status=Invoice.Status.OVERDUE).count()
    summary['overdue_amount'] = queryset.filter(
        status=Invoice.Status.OVERDUE
    ).aggregate(total=Sum('balance_due'))['total'] or ZERO

    return summary


def get_outstanding_by_customer(date_from=None, date_to=None):
    """
    Aggregated outstanding balance per registered customer — 'who owes us
    the most' view. Walk-in invoices are grouped separately since they
    have no persistent customer identity.
    """
    queryset = get_outstanding_invoices(date_from, date_to)

    registered = list(
        queryset.filter(customer_type=Invoice.CustomerType.REGISTERED)
        .values('customer__id', 'customer__full_name', 'customer__company_name')
        .annotate(total_owed=Sum('balance_due'), invoice_count=Count('id'))
        .order_by('-total_owed')
    )

    walk_in_total = queryset.filter(
        customer_type=Invoice.CustomerType.WALK_IN
    ).aggregate(total_owed=Sum('balance_due'), invoice_count=Count('id'))

    return {
        'registered_customers': registered,
        'walk_in_total_owed': walk_in_total['total_owed'] or ZERO,
        'walk_in_invoice_count': walk_in_total['invoice_count'] or 0,
    }


def get_aging_buckets(reference_date=None):
    """
    Standard accounts-receivable aging report: how overdue is each
    outstanding invoice, bucketed into ranges. Only considers invoices
    that have a due_date set (undated invoices are excluded from aging
    but still appear in get_outstanding_invoices).
    """
    reference_date = reference_date or timezone.localdate()
    queryset = get_outstanding_invoices().filter(due_date__isnull=False)

    buckets = {
        'current': {'label': 'Not yet due', 'count': 0, 'total': ZERO},
        '1_30': {'label': '1-30 days overdue', 'count': 0, 'total': ZERO},
        '31_60': {'label': '31-60 days overdue', 'count': 0, 'total': ZERO},
        '61_90': {'label': '61-90 days overdue', 'count': 0, 'total': ZERO},
        'over_90': {'label': 'Over 90 days overdue', 'count': 0, 'total': ZERO},
    }

    for invoice in queryset:
        days_overdue = (reference_date - invoice.due_date).days
        if days_overdue <= 0:
            key = 'current'
        elif days_overdue <= 30:
            key = '1_30'
        elif days_overdue <= 60:
            key = '31_60'
        elif days_overdue <= 90:
            key = '61_90'
        else:
            key = 'over_90'

        buckets[key]['count'] += 1
        buckets[key]['total'] += invoice.balance_due

    return buckets


# ---------------------------------------------------------------------------
# Dashboard-specific aggregates (consumed by the core app)
# ---------------------------------------------------------------------------

def get_dashboard_stats():
    """
    Snapshot of key numbers for the main dashboard: today's sales, this
    month's sales, outstanding total, low stock count, invoice status
    breakdown. Deliberately independent of any date-range filter form —
    always 'right now'.
    """
    from products.models import Product

    today = timezone.localdate()
    month_start = today.replace(day=1)

    today_sales = Invoice.objects.filter(
        issue_date=today
    ).exclude(status=Invoice.Status.CANCELLED).aggregate(
        total=Sum('total_amount'), count=Count('id')
    )
    month_sales = Invoice.objects.filter(
        issue_date__gte=month_start
    ).exclude(status=Invoice.Status.CANCELLED).aggregate(
        total=Sum('total_amount'), count=Count('id')
    )
    outstanding = get_outstanding_summary()

    return {
        'today_sales_total': today_sales['total'] or ZERO,
        'today_invoice_count': today_sales['count'] or 0,
        'month_sales_total': month_sales['total'] or ZERO,
        'month_invoice_count': month_sales['count'] or 0,
        'total_outstanding': outstanding['total_outstanding'],
        'overdue_invoice_count': outstanding['overdue_count'],
        'overdue_amount': outstanding['overdue_amount'],
        'low_stock_count': Product.objects.filter(
            track_stock=True, is_active=True, stock_quantity__lte=F('reorder_level')
        ).count(),
        'pending_invoice_count': Invoice.objects.filter(status=Invoice.Status.PENDING).count(),
    }



