from django.contrib import messages


class SuccessMessageMixin:
    """
    Generic mixin for CreateView/UpdateView subclasses across the project
    that want a one-line success flash message without repeating
    `messages.success(...)` in every form_valid(). Usage:

        class ProductCreateView(SuccessMessageMixin, CreateView):
            success_message = "Product '%(name)s' created successfully."
            ...

    The message string is formatted against the saved object's __dict__,
    so use %(field_name)s placeholders matching model fields.
    """
    success_message = ""

    def form_valid(self, form):
        response = super().form_valid(form)
        message = self.get_success_message(form.cleaned_data)
        if message:
            messages.success(self.request, message)
        return response

    def get_success_message(self, cleaned_data):
        try:
            return self.success_message % self.object.__dict__
        except (AttributeError, KeyError):
            return self.success_message


class PageTitleMixin:
    """
    Lets a view declare `page_title = "Products"` and have it available in
    templates as {{ page_title }} for the <title> tag / page header,
    without every view manually adding it to get_context_data.
    """
    page_title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.get_page_title()
        return context

    def get_page_title(self):
        return self.page_title


class StaffRequiredQuerysetMixin:
    """
    Optional mixin for ListViews that should only ever show records created
    by the logged-in user, unless they're an Admin/Manager (e.g. a future
    'my invoices today' cashier-scoped view). Not applied anywhere by
    default yet — available for views that need this scoping later.
    """
    owner_field = 'created_by'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_admin or user.is_manager:
            return queryset
        return queryset.filter(**{self.owner_field: user})






