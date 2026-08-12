from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView

from accounts.decorators import RoleRequiredMixin
from .models import Invoice
from .forms import InvoiceForm, InvoiceItemFormSet, InvoiceCancelForm, InvoiceSearchForm
from . import services


class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'invoices/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 25

    def get_queryset(self):
        queryset = Invoice.objects.select_related('customer').all()
        form = InvoiceSearchForm(self.request.GET or None)

        if form.is_valid():
            q = form.cleaned_data.get('q')
            status = form.cleaned_data.get('status')
            customer_type = form.cleaned_data.get('customer_type')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')

            if q:
                queryset = queryset.filter(
                    Q(invoice_number__icontains=q) |
                    Q(customer__full_name__icontains=q) |
                    Q(walk_in_customer_name__icontains=q)
                )
            if status:
                queryset = queryset.filter(status=status)
            if customer_type:
                queryset = queryset.filter(customer_type=customer_type)
            if date_from:
                queryset = queryset.filter(issue_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(issue_date__lte=date_to)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = InvoiceSearchForm(self.request.GET or None)
        return context


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'invoices/invoice_detail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product').all()
        # 'payments' related_name will exist once the payments app is built
        if hasattr(self.object, 'payments'):
            context['payments'] = self.object.payments.filter(is_voided=False).order_by('-payment_date')
        context['cancel_form'] = InvoiceCancelForm()
        return context


class InvoiceCreateView(LoginRequiredMixin, View):
    """
    Handles both the header form (InvoiceForm) and the item line formset
    (InvoiceItemFormSet) together, then delegates the actual atomic
    creation + stock deduction + totals calculation to
    services.create_invoice_with_items().
    """
    template_name = 'invoices/invoice_form.html'

    def get(self, request):
        invoice_form = InvoiceForm(initial={'customer_type': Invoice.CustomerType.WALK_IN})
        item_formset = InvoiceItemFormSet(prefix='items')
        return render(request, self.template_name, {
            'invoice_form': invoice_form,
            'item_formset': item_formset,
        })

    def post(self, request):
        invoice_form = InvoiceForm(request.POST)
        item_formset = InvoiceItemFormSet(request.POST, prefix='items')

        if invoice_form.is_valid() and item_formset.is_valid():
            invoice = invoice_form.save(commit=False)
            item_data_list = [
                form.to_item_data()
                for form in item_formset.forms
                if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
            ]
            try:
                invoice = services.create_invoice_with_items(invoice, item_data_list, request.user)
                messages.success(request, f"Invoice {invoice.invoice_number} created successfully.")
                return redirect('invoices:invoice_detail', pk=invoice.pk)
            except ValidationError as e:
                messages.error(request, "; ".join(e.messages) if hasattr(e, 'messages') else str(e))
        else:
            messages.error(request, "Please correct the errors below.")

        return render(request, self.template_name, {
            'invoice_form': invoice_form,
            'item_formset': item_formset,
        })


class InvoiceCancelView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Only Admins/Managers can cancel invoices (per role rules from accounts app)."""
    allowed_roles = ['ADMIN', 'MANAGER']

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        form = InvoiceCancelForm(request.POST)

        if form.is_valid():
            try:
                services.cancel_invoice(invoice, request.user, reason=form.cleaned_data['reason'])
                messages.success(request, f"Invoice {invoice.invoice_number} has been cancelled.")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please provide a reason for cancellation.")

        return redirect('invoices:invoice_detail', pk=pk)


class InvoicePDFView(LoginRequiredMixin, View):
    """
    Stub — wired up once the pdf_generation app is built. Will call
    pdf_generation.invoice_pdf.render_invoice_pdf(invoice) and return an
    HttpResponse with content_type='application/pdf'.
    """
    def get(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        from pdf_generation.invoice_pdf import render_invoice_pdf
        return render_invoice_pdf(invoice)


class InvoicePrintView(LoginRequiredMixin, DetailView):
    """Browser-printable HTML receipt/invoice view (uses window.print() client-side)."""
    model = Invoice
    template_name = 'invoices/invoice_print.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('product').all()
        if hasattr(self.object, 'payments'):
            context['payments'] = self.object.payments.filter(is_voided=False).order_by('-payment_date')
        return context