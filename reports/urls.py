from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('sales/', views.SalesReportView.as_view(), name='sales_report'),
    path('sales/api/trend/', views.SalesTrendAPIView.as_view(), name='api_sales_trend'),

    path('payments/', views.PaymentReportView.as_view(), name='payment_report'),
    path('payments/api/trend/', views.PaymentTrendAPIView.as_view(), name='api_payment_trend'),

    path('outstanding/', views.OutstandingReportView.as_view(), name='outstanding_report'),
    path('outstanding/api/aging/', views.AgingBucketsAPIView.as_view(), name='api_aging_buckets'),
]