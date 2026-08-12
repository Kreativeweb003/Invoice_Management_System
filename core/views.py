from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.utils import timezone

from invoices.models import Invoice
from payments.models import Payment
from products.models import Product
from reports import services as report_services


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main landing page after login. Pulls together:
      - KPI snapshot (today/month sales, outstanding, low stock, overdue)
      - Sales trend for the mini chart (last 14 days)
      - Recent invoices
      - Recent payments
      - Low stock alert list
      - Overdue invoices list

    All heavy aggregation is delegated to reports.services so these numbers
    always match the full report pages exactly — no duplicated query logic.
    """
    template_name = 'core/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # KPI cards — available to everyone, numbers just describe current state
        context['stats'] = report_services.get_dashboard_stats()

        # Recent activity — visible to all roles (cashiers need to see recent
        # invoices/payments they or others just processed)
        context['recent_invoices'] = (
            Invoice.objects.select_related('customer')
            .order_by('-created_at')[:8]
        )
        context['recent_payments'] = (
            Payment.objects.filter(is_voided=False)
            .select_related('invoice', 'received_by')
            .order_by('-created_at')[:8]
        )

        # Alerts
        context['low_stock_products'] = Product.objects.filter(
            track_stock=True, is_active=True
        ).order_by('stock_quantity')

        # Only show real low-stock items (property-based filter, since
        # comparing two model fields needs F() — already used in the queryset
        # inside report_services, here we just need the actual objects)
        context['low_stock_products'] = [
            p for p in context['low_stock_products'] if p.is_low_stock
        ][:8]

        context['overdue_invoices'] = (
            Invoice.objects.filter(status=Invoice.Status.OVERDUE)
            .select_related('customer')
            .order_by('due_date')[:8]
        )

        # Chart data for the dashboard's mini sales trend (last 14 days)
        fourteen_days_ago = timezone.localdate() - timezone.timedelta(days=13)
        context['sales_trend'] = report_services.get_sales_trend(
            date_from=fourteen_days_ago, date_to=timezone.localdate(), granularity='day'
        )

        # Role flags for template conditionals (e.g. hide report links from cashiers)
        context['can_view_reports'] = user.can_view_reports()
        context['can_manage_products'] = user.can_manage_products()
        context['can_manage_users'] = user.can_manage_users()

        return context