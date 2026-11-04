from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('signup/', views.sign_up, name='signup'),
    path('login/', views.MarketplaceLoginView.as_view(), name='login'),
    path('logout/', views.sign_out, name='logout'),
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),
    path('orders/', views.customer_orders, name='customer_orders'),
    path('vendor/', views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/products/add/', views.product_create, name='product_create'),
    path('vendor/products/<int:product_id>/edit/', views.product_edit, name='product_edit'),
    path('vendor/products/<int:product_id>/delete/', views.product_delete, name='product_delete'),
    path('vendor/orders/', views.vendor_orders, name='vendor_orders'),
]