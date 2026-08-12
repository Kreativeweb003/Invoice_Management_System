from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from accounts.decorators import RoleRequiredMixin
from .models import Customer
from .forms import CustomerForm, CustomerQuickCreateForm, CustomerSearchForm


class CustomerListView(LoginRequiredMixin, ListView):
    """
    Viewable by all authenticated roles (Cashiers need to browse customers
    when creating invoices). Editing/deleting is restricted separately below.
    """
    model = Customer
    template_name = 'customers/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 25

    def get_queryset(self):
        queryset = Customer.objects.all()
        form = CustomerSearchForm(self.request.GET or None)

        if form.is_valid():
            search = form.cleaned_data.get('q')
            status = form.cleaned_data.get('status')

            if search:
                queryset = queryset.filter(
                    Q(full_name__icontains=search) |
                    Q(company_name__icontains=search) |
                    Q(phone_number__icontains=search) |
                    Q(email__icontains=search)
                )
            if status == 'active':
                queryset = queryset.filter(is_active=True)
            elif status == 'inactive':
                queryset = queryset.filter(is_active=False)

        return queryset.order_by('full_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = CustomerSearchForm(self.request.GET or None)
        return context


class CustomerDetailView(LoginRequiredMixin, DetailView):
    """
    Shows customer profile plus their invoice history. The invoice queryset
    here uses the reverse relation from the invoices app (customer.invoices),
    which will exist once the invoices app is built.
    """
    model = Customer
    template_name = 'customers/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object
        # Guarded with hasattr so this view doesn't break before the
        # invoices app/migrations exist.
        if hasattr(customer, 'invoices'):
            context['invoices'] = customer.invoices.all().order_by('-created_at')[:20]
        return context


class CustomerCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    allowed_roles = ['ADMIN', 'MANAGER', 'CASHIER']  # cashiers can register walk-ins who want to become regulars
    template_name = 'customers/customer_form.html'
    success_url = reverse_lazy('customers:customer_list')

    def form_valid(self, form):
        customer = form.save(commit=False)
        customer.created_by = self.request.user
        customer.save()
        messages.success(self.request, f"Customer '{customer.display_name}' created successfully.")
        return redirect(customer.get_absolute_url())


class CustomerUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'customers/customer_form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Customer '{self.object.display_name}' updated successfully.")
        return response


class CustomerToggleActiveView(LoginRequiredMixin, RoleRequiredMixin, View):
    """
    Soft-delete mechanism. We never hard-delete customers because doing so
    would orphan or cascade-delete their historical invoices, violating the
    business rule that transaction history must be preserved.
    """
    allowed_roles = ['ADMIN', 'MANAGER']

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)
        customer.is_active = not customer.is_active
        customer.save(update_fields=['is_active'])
        state = "activated" if customer.is_active else "deactivated"
        messages.success(request, f"Customer '{customer.display_name}' has been {state}.")
        return redirect('customers:customer_detail', pk=pk)


# ---------------------------------------------------------------------------
# AJAX endpoints — used by the invoice creation screen
# ---------------------------------------------------------------------------

class CustomerSearchAPIView(LoginRequiredMixin, View):
    """
    Lightweight JSON search endpoint for the invoice form's customer
    autocomplete/select widget. Returns active customers only.
    """
    def get(self, request):
        query = request.GET.get('q', '').strip()
        queryset = Customer.objects.filter(is_active=True)

        if query:
            queryset = queryset.filter(
                Q(full_name__icontains=query) |
                Q(company_name__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(email__icontains=query)
            )

        results = [
            {
                'id': customer.pk,
                'text': customer.display_name,
                'phone': customer.phone_number,
                'email': customer.email,
            }
            for customer in queryset.order_by('full_name')[:15]
        ]
        return JsonResponse({'results': results})


class CustomerQuickCreateAPIView(LoginRequiredMixin, View):
    """
    Allows creating a minimal Customer record inline from the invoice
    creation form (e.g. a modal), without navigating away. Returns the
    new customer's id/display_name so the frontend JS can immediately
    select it in the invoice's customer dropdown.
    """
    def post(self, request):
        form = CustomerQuickCreateForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            return JsonResponse({
                'success': True,
                'customer': {
                    'id': customer.pk,
                    'text': customer.display_name,
                    'phone': customer.phone_number,
                    'email': customer.email,
                }
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)