from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import CheckoutForm, ProductForm, SignUpForm
from .models import Order, OrderItem, Product, UserProfile


def profile_for(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            if profile_for(request.user).role != role:
                messages.error(request, 'This page is not available for your account type.')
                return redirect('product_list')
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


class MarketplaceLoginView(LoginView):
    template_name = 'products/login.html'

    def get_default_redirect_url(self):
        if self.request.user.is_authenticated and profile_for(self.request.user).role == UserProfile.Role.VENDOR:
            return reverse('vendor_dashboard')
        return reverse('product_list')


def sign_up(request):
    if request.user.is_authenticated:
        return redirect('product_list')

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        if profile_for(user).role == UserProfile.Role.VENDOR:
            return redirect('vendor_dashboard')
        return redirect('product_list')
    return render(request, 'products/signup.html', {'form': form})


@require_POST
def sign_out(request):
    logout(request)
    return redirect('product_list')


def product_list(request):
    products = Product.objects.filter(stock__gt=0).select_related('vendor').order_by('-created_at')
    return render(request, 'products/product_list.html', {'products': products})


@role_required(UserProfile.Role.VENDOR)
def vendor_dashboard(request):
    products = Product.objects.filter(vendor=request.user).order_by('-created_at')
    sales = OrderItem.objects.filter(vendor=request.user).select_related(
        'order', 'order__customer', 'product',
    ).order_by('-order__created_at')
    return render(request, 'products/vendor_dashboard.html', {
        'products': products,
        'sales': sales[:20],
    })


@role_required(UserProfile.Role.VENDOR)
def product_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.vendor = request.user
        product.save()
        messages.success(request, 'Your product is now listed in the shop.')
        return redirect('vendor_dashboard')
    return render(request, 'products/product_form.html', {'form': form, 'heading': 'Add a product'})


@role_required(UserProfile.Role.VENDOR)
def product_edit(request, product_id):
    product = get_object_or_404(Product, pk=product_id, vendor=request.user)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Product details updated.')
        return redirect('vendor_dashboard')
    return render(request, 'products/product_form.html', {'form': form, 'heading': 'Edit product'})


@role_required(UserProfile.Role.VENDOR)
@require_POST
def product_delete(request, product_id):
    product = get_object_or_404(Product, pk=product_id, vendor=request.user)
    try:
        product.delete()
    except ProtectedError:
        messages.error(request, 'This product is part of an order and cannot be deleted. Set its stock to zero instead.')
    else:
        messages.success(request, 'Product removed from your listings.')
    return redirect('vendor_dashboard')


def cart_contents(request):
    cart = request.session.get('cart', {})
    products = Product.objects.filter(pk__in=cart).select_related('vendor')
    items = []
    total = Decimal('0.00')
    for product in products:
        quantity = cart.get(str(product.pk), 0)
        if not isinstance(quantity, int) or quantity < 1:
            continue
        subtotal = product.price * quantity
        items.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
        total += subtotal
    return items, total


def cart_view(request):
    items, total = cart_contents(request)
    return render(request, 'products/cart.html', {'items': items, 'total': total})


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    if not product.vendor_id or product.stock < 1:
        messages.error(request, 'This product is currently unavailable.')
        return redirect('product_list')
    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        quantity = 0
    cart = request.session.get('cart', {})
    current_quantity = cart.get(str(product.pk), 0)
    if quantity < 1 or current_quantity + quantity > product.stock:
        messages.error(request, 'Choose a quantity available in stock.')
    else:
        cart[str(product.pk)] = current_quantity + quantity
        request.session['cart'] = cart
        messages.success(request, f'{product.name} added to your cart.')
    return redirect('product_list')


@require_POST
def cart_update(request, product_id):
    cart = request.session.get('cart', {})
    key = str(product_id)
    if key not in cart:
        return redirect('cart')
    try:
        quantity = int(request.POST.get('quantity', '0'))
    except (TypeError, ValueError):
        quantity = -1
    if quantity == 0:
        cart.pop(key)
        messages.info(request, 'Product removed from your cart.')
    else:
        product = Product.objects.filter(pk=product_id, vendor__isnull=False).first()
        if quantity < 0 or product is None or quantity > product.stock:
            messages.error(request, 'Choose a quantity available in stock.')
        else:
            cart[key] = quantity
            messages.success(request, 'Cart updated.')
    request.session['cart'] = cart
    return redirect('cart')


@role_required(UserProfile.Role.CUSTOMER)
def checkout(request):
    items, total = cart_contents(request)
    if not items:
        messages.info(request, 'Your cart is empty.')
        return redirect('cart')

    form = CheckoutForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cart = request.session.get('cart', {})
        try:
            with transaction.atomic():
                products = list(
                    Product.objects.select_for_update()
                    .filter(pk__in=cart, vendor__isnull=False)
                    .order_by('pk')
                )
                if len(products) != len(cart):
                    raise ValueError('One or more products in your cart are no longer available.')
                quantities = {str(product.pk): cart[str(product.pk)] for product in products}
                if any(quantities[str(product.pk)] > product.stock for product in products):
                    raise ValueError('Stock changed for one or more products. Update your cart and try again.')

                order = form.save(commit=False)
                order.customer = request.user
                order.save()
                for product in products:
                    quantity = quantities[str(product.pk)]
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        vendor=product.vendor,
                        product_name=product.name,
                        unit_price=product.price,
                        quantity=quantity,
                    )
                    product.stock -= quantity
                    product.save(update_fields=['stock'])
        except ValueError as error:
            messages.error(request, str(error))
            return redirect('cart')

        request.session['cart'] = {}
        messages.success(request, f'Order #{order.pk} placed successfully.')
        return redirect('customer_orders')
    return render(request, 'products/checkout.html', {'form': form, 'items': items, 'total': total})


@role_required(UserProfile.Role.CUSTOMER)
def customer_orders(request):
    orders = Order.objects.filter(customer=request.user).prefetch_related('items').order_by('-created_at')
    return render(request, 'products/customer_orders.html', {'orders': orders})


def vendor_orders(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if profile_for(request.user).role != UserProfile.Role.VENDOR:
        messages.error(request, 'Sign in with a wholesaler account to view sales.')
        return redirect('product_list')
    sales = OrderItem.objects.filter(vendor=request.user).select_related(
        'order', 'order__customer', 'product',
    ).order_by('-order__created_at')
    return render(request, 'products/vendor_orders.html', {'sales': sales})
