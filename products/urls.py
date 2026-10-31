# product/urls.py

from django.contrib.admin import views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
]