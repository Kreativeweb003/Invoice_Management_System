from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required


def role_required(*allowed_roles):
    """
    Function-based view decorator restricting access to specific roles.

    Usage:
        @role_required('ADMIN')
        def some_view(request): ...

        @role_required('ADMIN', 'MANAGER')
        def another_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                raise PermissionDenied(
                    "You do not have permission to access this page."
                )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


# Convenience shortcuts for the most common checks
admin_required = role_required('ADMIN')
manager_or_admin_required = role_required('ADMIN', 'MANAGER')


class RoleRequiredMixin:
    """
    Class-based view mixin restricting access to specific roles.

    Usage:
        class SomeView(RoleRequiredMixin, ListView):
            allowed_roles = ['ADMIN', 'MANAGER']
            ...

    Must be combined with LoginRequiredMixin (placed before it in MRO), e.g.:
        class SomeView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        if self.allowed_roles and request.user.role not in self.allowed_roles:
            raise PermissionDenied(
                "You do not have permission to access this page."
            )
        return super().dispatch(request, *args, **kwargs)