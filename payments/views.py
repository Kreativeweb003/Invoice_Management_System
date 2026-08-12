from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import redirect, get_object_or_404, render
from django.views import View
from django.views.generic import ListView, DetailView

from accounts.decorators import RoleRequiredMixin
from invoices.models import Invoice
from .models import Payment
from .forms import PaymentForm, PaymentVoidForm, PaymentSearchForm
from . import services


class PaymentCreateView(LoginRequiredMixin, View):
    """
    Nested under an invoice: /invoices/<invoice_pk>/payments/add/
    Renders a small form (amount, method, reference, notes) and delegates
    the actual balance-checked creation to services.record_payment().
    """
    template_name = 'payments/payment_form.html'

    def get(self, request, invoice_pk):
        invoice = get_object_or_404(Invoice, pk=invoice_pk)
        if invoice.status == Invoice.Status.CANCELLED:
            messages.error(request, "Cannot record a payment against a cancelled invoice.")
            return redirect('invoices:invoice_detail', pk=invoice.pk)
        if invoice.balance_due <= 0:
            messages.info(request, "This invoice is already fully paid.")
            return redirect('invoices:invoice_detail', pk=invoice.pk)

        form = PaymentForm(invoice=invoice)
        return render(request, self.template_name, {'form': form, 'invoice': invoice})

    def post(self, request, invoice_pk):
        invoice = get_object_or_404(Invoice, pk=invoice_pk)
        form = PaymentForm(request.POST, invoice=invoice)

        if form.is_valid():
            try:
                payment = services.record_payment(
                    invoice=invoice,
                    amount=form.cleaned_data['amount'],
                    method=form.cleaned_data['method'],
                    user=request.user,
                    payment_date=form.cleaned_data.get('payment_date'),
                    reference_number=form.cleaned_data.get('reference_number', ''),
                    notes=form.cleaned_data.get('notes', ''),
                )
                messages.success(
                    request,
                    f"Payment {payment.payment_number} of {payment.amount} recorded successfully."
                )
                return redirect('invoices:invoice_detail', pk=invoice.pk)
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please correct the errors below.")

        return render(request, self.template_name, {'form': form, 'invoice': invoice})


class PaymentVoidView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Only Admins/Managers can void a payment."""
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'payments/payment_void_form.html'

    def get(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        form = PaymentVoidForm()
        return render(request, self.template_name, {'form': form, 'payment': payment})

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk)
        form = PaymentVoidForm(request.POST)

        if form.is_valid():
            try:
                services.void_payment(payment, request.user, form.cleaned_data['reason'])
                messages.success(request, f"Payment {payment.payment_number} has been voided.")
                return redirect('invoices:invoice_detail', pk=payment.invoice_id)
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please provide a reason for voiding this payment.")

        return render(request, self.template_name, {'form': form, 'payment': payment})


class PaymentListView(LoginRequiredMixin, ListView):
    """
    Global payment log across all invoices — distinct from the payment
    history shown on an individual invoice detail page. Useful for
    cashier shift reconciliation and the payments report.
    """
    model = Payment
    template_name = 'payments/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 30

    def get_queryset(self):
        queryset = Payment.objects.select_related('invoice', 'received_by').all()
        form = PaymentSearchForm(self.request.GET or None)

        if form.is_valid():
            q = form.cleaned_data.get('q')
            method = form.cleaned_data.get('method')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            include_voided = form.cleaned_data.get('include_voided')

            if not include_voided:
                queryset = queryset.filter(is_voided=False)
            if q:
                queryset = queryset.filter(
                    Q(payment_number__icontains=q) |
                    Q(invoice__invoice_number__icontains=q) |
                    Q(reference_number__icontains=q)
                )
            if method:
                queryset = queryset.filter(method=method)
            if date_from:
                queryset = queryset.filter(payment_date__gte=date_from)
            if date_to:
                queryset = queryset.filter(payment_date__lte=date_to)

        return queryset.order_by('-payment_date', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PaymentSearchForm(self.request.GET or None)
        return context


class PaymentDetailView(LoginRequiredMixin, DetailView):
    model = Payment
    template_name = 'payments/payment_detail.html'
    context_object_name = 'payment'


class PaymentReceiptView(LoginRequiredMixin, DetailView):
    """Printable receipt for a single payment (client-side window.print())."""
    model = Payment
    template_name = 'payments/payment_receipt.html'
    context_object_name = 'payment'


