from django.urls import path
from . import views

app_name = 'invoices'

urlpatterns = [
    path('', views.InvoiceListView.as_view(), name='invoice_list'),
    path('create/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('<int:pk>/', views.InvoiceDetailView.as_view(), name='invoice_detail'),
    path('<int:pk>/cancel/', views.InvoiceCancelView.as_view(), name='invoice_cancel'),
    path('<int:pk>/pdf/', views.InvoicePDFView.as_view(), name='invoice_pdf'),
    path('<int:pk>/print/', views.InvoicePrintView.as_view(), name='invoice_print'),
]