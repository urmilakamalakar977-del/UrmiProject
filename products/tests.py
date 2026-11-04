from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import override_settings

from .models import Order, OrderItem, Product, UserProfile


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ProductListTests(TestCase):
    def test_product_list_displays_products(self):
        vendor = User.objects.create_user(username='vendor', password='long-test-password')
        UserProfile.objects.create(user=vendor, role=UserProfile.Role.VENDOR)
        Product.objects.create(
            vendor=vendor,
            name='Test product',
            description='A product for the catalog test.',
            price='9.99',
            stock=3,
        )

        response = self.client.get(reverse('product_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test product')

    def test_out_of_stock_products_are_not_listed(self):
        vendor = User.objects.create_user(username='vendor', password='long-test-password')
        Product.objects.create(
            vendor=vendor,
            name='Unavailable product',
            description='Not available.',
            price='9.99',
            stock=0,
        )

        response = self.client.get(reverse('product_list'))

        self.assertNotContains(response, 'Unavailable product')


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class MarketplaceFlowTests(TestCase):
    def setUp(self):
        self.vendor_one = User.objects.create_user(username='seller-one', password='test-password-123')
        self.vendor_two = User.objects.create_user(username='seller-two', password='test-password-123')
        self.customer = User.objects.create_user(username='buyer', password='test-password-123')
        UserProfile.objects.create(user=self.vendor_one, role=UserProfile.Role.VENDOR)
        UserProfile.objects.create(user=self.vendor_two, role=UserProfile.Role.VENDOR)
        UserProfile.objects.create(user=self.customer, role=UserProfile.Role.CUSTOMER)
        self.product_one = Product.objects.create(
            vendor=self.vendor_one,
            name='Green mug',
            description='Handmade mug',
            price='12.50',
            stock=5,
        )
        self.product_two = Product.objects.create(
            vendor=self.vendor_two,
            name='Linen bag',
            description='Reusable bag',
            price='8.00',
            stock=4,
        )

    def test_vendor_signup_creates_vendor_and_redirects_to_dashboard(self):
        response = self.client.post(reverse('signup'), {
            'username': 'new-wholesaler',
            'email': 'vendor@example.com',
            'role': UserProfile.Role.VENDOR,
            'password1': 'GoodPass!3478',
            'password2': 'GoodPass!3478',
        })

        self.assertRedirects(response, reverse('vendor_dashboard'))
        self.assertEqual(
            UserProfile.objects.get(user__username='new-wholesaler').role,
            UserProfile.Role.VENDOR,
        )

    def test_wholesaler_signup_and_login_are_role_specific(self):
        response = self.client.post(reverse('vendor_signup'), {
            'username': 'dedicated-wholesaler',
            'email': 'dedicated@example.com',
            'role': UserProfile.Role.CUSTOMER,
            'password1': 'GoodPass!3478',
            'password2': 'GoodPass!3478',
        })

        self.assertRedirects(response, reverse('vendor_dashboard'))
        self.assertEqual(
            UserProfile.objects.get(user__username='dedicated-wholesaler').role,
            UserProfile.Role.VENDOR,
        )

        self.client.logout()
        response = self.client.post(reverse('vendor_login'), {
            'username': 'seller-one',
            'password': 'test-password-123',
        })
        self.assertRedirects(response, reverse('vendor_dashboard'))

        self.client.logout()
        response = self.client.post(reverse('vendor_login'), {
            'username': 'buyer',
            'password': 'test-password-123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This sign-in page is for wholesaler accounts.')

    def test_vendor_can_create_products_but_not_edit_another_vendors_product(self):
        self.client.force_login(self.vendor_one)

        response = self.client.post(reverse('product_create'), {
            'name': 'Clay bowl',
            'description': 'A handmade serving bowl.',
            'price': '19.99',
            'stock': '6',
        })

        self.assertRedirects(response, reverse('vendor_dashboard'))
        self.assertTrue(Product.objects.filter(vendor=self.vendor_one, name='Clay bowl').exists())
        response = self.client.get(reverse('product_edit', args=[self.product_two.pk]))
        self.assertEqual(response.status_code, 404)

    def test_vendor_cannot_list_a_product_with_a_nonpositive_price(self):
        self.client.force_login(self.vendor_one)

        response = self.client.post(reverse('product_create'), {
            'name': 'Free mug',
            'description': 'A test listing.',
            'price': '0.00',
            'stock': '1',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Product.objects.filter(vendor=self.vendor_one, name='Free mug').exists())

    def test_customer_cannot_open_seller_dashboard(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse('vendor_dashboard'))

        self.assertRedirects(response, reverse('product_list'))

    def test_anonymous_vendor_dashboard_redirects_to_login(self):
        response = self.client.get(reverse('vendor_dashboard'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('vendor_dashboard')}",
        )

    def test_customer_can_checkout_from_multiple_vendors_as_one_order(self):
        self.client.force_login(self.customer)
        self.client.post(reverse('cart_add', args=[self.product_one.pk]), {'quantity': '2'})
        self.client.post(reverse('cart_add', args=[self.product_two.pk]), {'quantity': '1'})

        response = self.client.post(reverse('checkout'), {
            'shipping_address': '10 Market Street, Springfield',
        })

        order = Order.objects.get(customer=self.customer)
        self.assertRedirects(response, reverse('customer_orders'))
        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total, 33)
        self.assertEqual(self.product_one.stock - 2, Product.objects.get(pk=self.product_one.pk).stock)
        self.assertEqual(self.product_two.stock - 1, Product.objects.get(pk=self.product_two.pk).stock)
        self.assertEqual(OrderItem.objects.filter(vendor=self.vendor_one).count(), 1)
        self.assertEqual(OrderItem.objects.filter(vendor=self.vendor_two).count(), 1)
        self.assertEqual(self.client.session['cart'], {})

        self.client.force_login(self.vendor_one)
        response = self.client.get(reverse('vendor_orders'))
        self.assertContains(response, 'Green mug')
        self.assertNotContains(response, 'Linen bag')

    def test_checkout_rejects_cart_when_stock_has_changed(self):
        self.client.force_login(self.customer)
        self.client.post(reverse('cart_add', args=[self.product_one.pk]), {'quantity': '2'})
        Product.objects.filter(pk=self.product_one.pk).update(stock=1)

        response = self.client.post(reverse('checkout'), {
            'shipping_address': '10 Market Street, Springfield',
        })

        self.assertRedirects(response, reverse('cart'))
        self.assertFalse(Order.objects.exists())
