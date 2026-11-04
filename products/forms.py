from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Order, Product, UserProfile


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=UserProfile.Role.choices)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role')

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserProfile.objects.create(user=user, role=self.cleaned_data['role'])
        return user


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('name', 'description', 'price', 'stock', 'image')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('shipping_address',)
        widgets = {
            'shipping_address': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Street, city, state, postal code',
            }),
        }
