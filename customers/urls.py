from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.CustomerListView.as_view(), name='customer_list'),
    path('create/', views.CustomerCreateView.as_view(), name='customer_create'),
    path('<int:pk>/', views.CustomerDetailView.as_view(), name='customer_detail'),
    path('<int:pk>/edit/', views.CustomerUpdateView.as_view(), name='customer_update'),
    path('<int:pk>/toggle-active/', views.CustomerToggleActiveView.as_view(), name='customer_toggle_active'),

    # AJAX endpoints (used by the invoice creation form)
    path('api/search/', views.CustomerSearchAPIView.as_view(), name='api_customer_search'),
    path('api/quick-create/', views.CustomerQuickCreateAPIView.as_view(), name='api_customer_quick_create'),
]