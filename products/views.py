from django.shortcuts import render
from .models import Product


def product_list(request):
    # Fetch all products ordered by the newest addition first
    products = Product.objects.all().order_by('-created_at')
    
    context = {
        'products': products
    }
    return render(request, 'products/product_list.html', context)