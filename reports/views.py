from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from accounts.decorators import RoleRequiredMixin
from . import services
from .forms import SalesReportForm, PaymentReportForm, OutstandingReportForm


# ---------------------------------------------------------------------------
# Sales report
# ---------------------------------------------------------------------------

class SalesReportView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    """Full sales report page: KPIs, trend chart data, top products, top customers."""
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'reports/sales_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = SalesReportForm(self.request.GET or None)
        date_from = date_to = None
        granularity = 'day'
        include_cancelled = False

        if form.is_valid():
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            granularity = form.cleaned_data.get('granularity') or 'day'
            include_cancelled = form.cleaned_data.get('include_cancelled')

        context['form'] = form
        context['summary'] = services.get_sales_summary(date_from, date_to, include_cancelled)
        context['sales_by_status'] = services.get_sales_by_status(date_from, date_to)
        context['sales_trend'] = services.get_sales_trend(date_from, date_to, granularity)
        context['top_products'] = services.get_top_selling_products(date_from, date_to)
        context['sales_by_customer_type'] = services.get_sales_by_customer_type(date_from, date_to)
        context['top_customers'] = services.get_top_customers(date_from, date_to)
        return context


class SalesTrendAPIView(LoginRequiredMixin, RoleRequiredMixin, View):
    """JSON endpoint feeding the Chart.js sales trend line chart."""
    allowed_roles = ['ADMIN', 'MANAGER']

    def get(self, request):
        form = SalesReportForm(request.GET or None)
        date_from = date_to = None
        granularity = 'day'
        if form.is_valid():
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            granularity = form.cleaned_data.get('granularity') or 'day'

        trend = services.get_sales_trend(date_from, date_to, granularity)
        return JsonResponse({
            'labels': [str(row['period']) for row in trend],
            'sales': [str(row['total_sales']) for row in trend],
            'invoice_counts': [row['invoice_count'] for row in trend],
        })


# ---------------------------------------------------------------------------
# Payment report
# ---------------------------------------------------------------------------

class PaymentReportView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'reports/payment_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = PaymentReportForm(self.request.GET or None)
        date_from = date_to = None
        granularity = 'day'

        if form.is_valid():
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            granularity = form.cleaned_data.get('granularity') or 'day'

        context['form'] = form
        context['summary'] = services.get_payment_summary(date_from, date_to)
        context['payments_by_method'] = services.get_payments_by_method(date_from, date_to)
        context['payment_trend'] = services.get_payment_trend(date_from, date_to, granularity)
        context['collections_by_staff'] = services.get_daily_collections_by_staff(date_from, date_to)
        return context


class PaymentTrendAPIView(LoginRequiredMixin, RoleRequiredMixin, View):
    """JSON endpoint feeding the Chart.js payment collections chart."""
    allowed_roles = ['ADMIN', 'MANAGER']

    def get(self, request):
        form = PaymentReportForm(request.GET or None)
        date_from = date_to = None
        granularity = 'day'
        if form.is_valid():
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            granularity = form.cleaned_data.get('granularity') or 'day'

        trend = services.get_payment_trend(date_from, date_to, granularity)
        return JsonResponse({
            'labels': [str(row['period']) for row in trend],
            'collected': [str(row['total_collected']) for row in trend],
            'payment_counts': [row['payment_count'] for row in trend],
        })


# ---------------------------------------------------------------------------
# Outstanding balance report
# ---------------------------------------------------------------------------

class OutstandingReportView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'reports/outstanding_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = OutstandingReportForm(self.request.GET or None)
        date_from = date_to = None
        only_overdue = False

        if form.is_valid():
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            only_overdue = form.cleaned_data.get('only_overdue')

        context['form'] = form
        context['summary'] = services.get_outstanding_summary(date_from, date_to)
        context['outstanding_invoices'] = services.get_outstanding_invoices(date_from, date_to, only_overdue)
        context['outstanding_by_customer'] = services.get_outstanding_by_customer(date_from, date_to)
        context['aging_buckets'] = services.get_aging_buckets()
        return context


class AgingBucketsAPIView(LoginRequiredMixin, RoleRequiredMixin, View):
    """JSON endpoint feeding the Chart.js aging-buckets bar chart."""
    allowed_roles = ['ADMIN', 'MANAGER']

    def get(self, request):
        buckets = services.get_aging_buckets()
        return JsonResponse({
            'labels': [b['label'] for b in buckets.values()],
            'counts': [b['count'] for b in buckets.values()],
            'totals': [str(b['total']) for b in buckets.values()],
        })