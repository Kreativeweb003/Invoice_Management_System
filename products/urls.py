from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    # Products
    path('', views.ProductListView.as_view(), name='product_list'),
    path('create/', views.ProductCreateView.as_view(), name='product_create'),
    path('<int:pk>/', views.ProductDetailView.as_view(), name='product_detail'),
    path('<int:pk>/edit/', views.ProductUpdateView.as_view(), name='product_update'),
    path('<int:pk>/toggle-active/', views.ProductToggleActiveView.as_view(), name='product_toggle_active'),
    path('<int:pk>/adjust-stock/', views.StockAdjustmentView.as_view(), name='product_adjust_stock'),

    # Categories
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),

    # AJAX endpoints (used by the invoice creation form)
    path('api/search/', views.ProductSearchAPIView.as_view(), name='api_product_search'),
    path('api/<int:pk>/check-stock/', views.ProductStockCheckAPIView.as_view(), name='api_check_stock'),
]