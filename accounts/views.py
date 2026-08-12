from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect, get_object_or_404, render
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.contrib.auth.forms import PasswordChangeForm, AdminPasswordChangeForm

from .models import CustomUser
from .forms import LoginForm, StaffCreationForm, StaffUpdateForm, ProfileUpdateForm
from .decorators import RoleRequiredMixin


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class CustomLoginView(auth_views.LoginView):
    """Handles staff login. Redirects to LOGIN_REDIRECT_URL (core:dashboard)
    on success, or to ?next= if provided."""
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True


class CustomLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy('accounts:login')


# ---------------------------------------------------------------------------
# Staff / user management (Admin only)
# ---------------------------------------------------------------------------

class UserListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = CustomUser
    allowed_roles = ['ADMIN']
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        queryset = CustomUser.objects.all().order_by('-date_joined')
        search = self.request.GET.get('q')
        role = self.request.GET.get('role')

        if search:
            queryset = queryset.filter(
                models_q_search(search)
            )
        if role:
            queryset = queryset.filter(role=role)
        return queryset


def models_q_search(search_term):
    """Small helper to keep the queryset filter readable above."""
    from django.db.models import Q
    return (
        Q(username__icontains=search_term) |
        Q(first_name__icontains=search_term) |
        Q(last_name__icontains=search_term) |
        Q(email__icontains=search_term)
    )


class UserDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = CustomUser
    allowed_roles = ['ADMIN']
    template_name = 'accounts/user_detail.html'
    context_object_name = 'staff_user'


class UserCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = CustomUser
    allowed_roles = ['ADMIN']
    form_class = StaffCreationForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.created_by = self.request.user
        user.save()
        messages.success(self.request, f"Staff account '{user.username}' created successfully.")
        return redirect(self.success_url)


class UserUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = CustomUser
    allowed_roles = ['ADMIN']
    form_class = StaffUpdateForm
    template_name = 'accounts/user_form.html'
    success_url = reverse_lazy('accounts:user_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Staff account '{self.object.username}' updated successfully.")
        return response


class UserResetPasswordView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Allows an Admin to force-set a new password for a staff account
    (e.g. after a forgotten password) without knowing the old one."""
    allowed_roles = ['ADMIN']
    template_name = 'accounts/user_reset_password.html'

    def get(self, request, pk):
        target_user = get_object_or_404(CustomUser, pk=pk)
        form = AdminPasswordChangeForm(target_user)
        return render(request, self.template_name, {'form': form, 'target_user': target_user})

    def post(self, request, pk):
        target_user = get_object_or_404(CustomUser, pk=pk)
        form = AdminPasswordChangeForm(target_user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Password reset for '{target_user.username}'.")
            return redirect('accounts:user_detail', pk=target_user.pk)
        return render(request, self.template_name, {'form': form, 'target_user': target_user})


class UserToggleActiveView(LoginRequiredMixin, RoleRequiredMixin, View):
    """Quick action to enable/disable a staff account without deleting it —
    preserves history on invoices/payments they created."""
    allowed_roles = ['ADMIN']

    def post(self, request, pk):
        target_user = get_object_or_404(CustomUser, pk=pk)
        if target_user == request.user:
            messages.error(request, "You cannot disable your own account.")
        else:
            target_user.is_disabled = not target_user.is_disabled
            target_user.save(update_fields=['is_disabled'])
            state = "disabled" if target_user.is_disabled else "enabled"
            messages.success(request, f"Account '{target_user.username}' has been {state}.")
        return redirect('accounts:user_detail', pk=pk)


# ---------------------------------------------------------------------------
# Self-service profile (any authenticated user)
# ---------------------------------------------------------------------------

class ProfileView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = 'accounts/profile.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)


class ChangePasswordView(LoginRequiredMixin, View):
    template_name = 'accounts/change_password.html'

    def get(self, request):
        form = PasswordChangeForm(user=request.user)
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # keep user logged in
            messages.success(request, "Password changed successfully.")
            return redirect('accounts:profile')
        return render(request, self.template_name, {'form': form})











