from django.test import TestCase
from django.urls import reverse

from .models import Product


class ProductListTests(TestCase):
    def test_product_list_displays_products(self):
        Product.objects.create(
            name='Test product',
            description='A product for the catalog test.',
            price='9.99',
        )

        response = self.client.get(reverse('product_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test product')
