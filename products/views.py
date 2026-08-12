from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q, F
from django.http import JsonResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from accounts.decorators import RoleRequiredMixin
from .models import Product, Category
from .forms import ProductForm, CategoryForm, StockAdjustmentForm, ProductSearchForm


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

class ProductListView(LoginRequiredMixin, ListView):
    """Viewable by all roles — cashiers need this to build invoices."""
    model = Product
    template_name = 'products/product_list.html'
    context_object_name = 'products'
    paginate_by = 25

    def get_queryset(self):
        queryset = Product.objects.select_related('category').all()
        form = ProductSearchForm(self.request.GET or None)

        if form.is_valid():
            search = form.cleaned_data.get('q')
            category = form.cleaned_data.get('category')
            stock_status = form.cleaned_data.get('stock_status')

            if search:
                queryset = queryset.filter(
                    Q(name__icontains=search) |
                    Q(sku__icontains=search) |
                    Q(description__icontains=search)
                )
            if category:
                queryset = queryset.filter(category=category)

            if stock_status == 'out_of_stock':
                queryset = queryset.filter(track_stock=True, stock_quantity__lte=0)
            elif stock_status == 'low_stock':
                queryset = queryset.filter(
                    track_stock=True, stock_quantity__gt=0, stock_quantity__lte=F('reorder_level')
                )
            elif stock_status == 'in_stock':
                queryset = queryset.filter(track_stock=True, stock_quantity__gt=F('reorder_level'))

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ProductSearchForm(self.request.GET or None)
        context['low_stock_count'] = Product.objects.filter(
            track_stock=True, stock_quantity__lte=F('reorder_level'), is_active=True
        ).count()
        return context


class ProductDetailView(LoginRequiredMixin, DetailView):
    model = Product
    template_name = 'products/product_detail.html'
    context_object_name = 'product'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stock_movements'] = self.object.stock_movements.all()[:20]
        context['adjustment_form'] = StockAdjustmentForm()
        return context


class ProductCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'products/product_form.html'
    success_url = reverse_lazy('products:product_list')

    def form_valid(self, form):
        product = form.save(commit=False)
        product.created_by = self.request.user
        product.save()

        # Log opening stock as a movement for audit consistency, if any.
        if product.track_stock and product.stock_quantity > 0:
            from .models import StockMovement
            StockMovement.objects.create(
                product=product,
                movement_type=StockMovement.MovementType.PURCHASE,
                quantity=product.stock_quantity,
                resulting_stock=product.stock_quantity,
                reference='Opening stock',
                notes='Initial stock recorded at product creation.',
                created_by=self.request.user,
            )

        messages.success(self.request, f"Product '{product.name}' created successfully.")
        return redirect(product.get_absolute_url())


class ProductUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """
    NOTE: stock_quantity is intentionally left editable on the form for
    convenience, but in the template this field should be rendered read-only
    with a note pointing users to 'Adjust Stock' instead, so every change
    post-creation flows through StockMovement. We still guard server-side:
    """
    model = Product
    form_class = ProductForm
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'products/product_form.html'

    def form_valid(self, form):
        # Prevent silent stock_quantity edits bypassing the audit trail.
        form.instance.stock_quantity = self.get_object().stock_quantity
        response = super().form_valid(form)
        messages.success(self.request, f"Product '{self.object.name}' updated successfully.")
        return response


class ProductToggleActiveView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Soft-delete only — old invoices reference this product's frozen
    price snapshot, so the Product row itself must never be hard-deleted."""
    allowed_roles = ['ADMIN', 'MANAGER']

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        product.is_active = not product.is_active
        product.save(update_fields=['is_active'])
        state = "activated" if product.is_active else "deactivated"
        messages.success(request, f"Product '{product.name}' has been {state}.")
        return redirect('products:product_detail', pk=pk)


class StockAdjustmentView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Dedicated endpoint for adjusting stock — the only sanctioned path
    besides sales/returns processed automatically by the invoices app."""
    allowed_roles = ['ADMIN', 'MANAGER']

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        form = StockAdjustmentForm(request.POST)

        if form.is_valid():
            try:
                product.adjust_stock(
                    quantity=form.cleaned_data['quantity'],
                    movement_type=form.cleaned_data['movement_type'],
                    reference=form.cleaned_data['reference'],
                    notes=form.cleaned_data['notes'],
                    user=request.user,
                )
                messages.success(request, f"Stock adjusted for '{product.name}'. New stock: {product.stock_quantity}.")
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Invalid stock adjustment data.")

        return redirect('products:product_detail', pk=pk)


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = 'products/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        return Category.objects.all().order_by('name')


class CategoryCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'products/category_form.html'
    success_url = reverse_lazy('products:category_list')

    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' created successfully.")
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    allowed_roles = ['ADMIN', 'MANAGER']
    template_name = 'products/category_form.html'
    success_url = reverse_lazy('products:category_list')

    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' updated successfully.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# AJAX endpoints — used by the invoice creation screen
# ---------------------------------------------------------------------------

class ProductSearchAPIView(LoginRequiredMixin, View):
    """
    JSON search endpoint for the invoice line-item product picker.
    Returns current price + available stock so the frontend JS can validate
    quantity in real time before submission (backend re-validates too).
    """
    def get(self, request):
        query = request.GET.get('q', '').strip()
        queryset = Product.objects.filter(is_active=True)

        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(sku__icontains=query)
            )

        results = [
            {
                'id': product.pk,
                'text': f"{product.name} ({product.sku})",
                'price': str(product.price),
                'stock_quantity': str(product.stock_quantity),
                'track_stock': product.track_stock,
                'unit': product.get_unit_display(),
            }
            for product in queryset.order_by('name')[:15]
        ]
        return JsonResponse({'results': results})


class ProductStockCheckAPIView(LoginRequiredMixin, View):
    """
    Used by invoice form JS to validate a requested quantity against live
    stock before the invoice is submitted (a convenience UX check — the
    real, authoritative check happens server-side in invoices/services.py).
    """
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        requested_qty = request.GET.get('quantity', 0)
        try:
            requested_qty = float(requested_qty)
        except ValueError:
            requested_qty = 0

        return JsonResponse({
            'sufficient': product.has_sufficient_stock(requested_qty),
            'available_stock': str(product.stock_quantity),
            'track_stock': product.track_stock,
        })






