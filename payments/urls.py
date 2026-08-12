from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Global payment log
    path('', views.PaymentListView.as_view(), name='payment_list'),
    path('<int:pk>/', views.PaymentDetailView.as_view(), name='payment_detail'),
    path('<int:pk>/void/', views.PaymentVoidView.as_view(), name='payment_void'),
    path('<int:pk>/receipt/', views.PaymentReceiptView.as_view(), name='payment_receipt'),

    # Invoice-scoped creation
    path('invoice/<int:invoice_pk>/add/', views.PaymentCreateView.as_view(), name='payment_create'),
]