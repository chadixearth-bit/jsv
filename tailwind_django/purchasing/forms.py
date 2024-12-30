from django import forms
from django.db.models.query import QuerySet
from typing import Any
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, Delivery
from inventory.models import InventoryItem
import json

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'email', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}),
            'contact_person': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}),
            'email': forms.EmailInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}),
            'phone': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}),
        }

class PurchaseOrderForm(forms.ModelForm):
    verification_file = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
        'accept': 'image/*,.pdf'
    }))

    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'warehouse', 'order_date', 'expected_delivery_date', 'notes', 'verification_file']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500', 'required': True}),
            'warehouse': forms.Select(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500', 'required': True}),
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500', 'required': True}),
            'expected_delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500', 'required': True}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and not user.is_superuser and not user.customuser.role == 'admin':
            self.fields['warehouse'].queryset = user.warehouses.all()

    def clean(self) -> dict:
        cleaned_data = super().clean()
        if cleaned_data.get('expected_delivery_date') and cleaned_data.get('order_date'):
            if cleaned_data['expected_delivery_date'] < cleaned_data['order_date']:
                raise forms.ValidationError("Expected delivery date cannot be earlier than the order date.")
        return cleaned_data

    def save(self, commit: bool = True) -> 'PurchaseOrder':
        instance = super().save(commit=False)
        if commit:
            instance.save()
        return instance

class PurchaseOrderItemForm(forms.ModelForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Type hint for queryset to help type checker
        self.fields['item'].queryset = InventoryItem.objects.filter(availability=True)  # type: ignore
        self.fields['item'].label_from_instance = lambda obj: f"{obj.item_name} ({obj.item_code})"

    def clean(self) -> dict:
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')

        if quantity and quantity < 1:
            raise forms.ValidationError("Quantity must be at least 1")
        
        if unit_price and unit_price <= 0:
            raise forms.ValidationError("Unit price must be greater than 0")

        if quantity and unit_price:
            cleaned_data['subtotal'] = quantity * unit_price

        return cleaned_data

    class Meta:
        model = PurchaseOrderItem
        fields = ['item', 'brand', 'model_name', 'quantity', 'unit_price']
        widgets = {
            'item': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'data-placeholder': 'Select an item...'
            }),
            'brand': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'required': True,
                'placeholder': 'Enter brand name'
            }),
            'model_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'required': True,
                'placeholder': 'Enter model name'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'min': '1',
                'placeholder': 'Enter quantity'
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'min': '0.01',
                'step': '0.01',
                'placeholder': 'Enter unit price'
            }),
        }

class DeliveryReceiptForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ['receipt_photo', 'delivery_confirmation_file', 'notes']
        widgets = {
            'receipt_photo': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'accept': 'image/*',
                'data-max-size': '5242880'  # 5MB in bytes
            }),
            'delivery_confirmation_file': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'accept': '.pdf,.doc,.docx,image/*',
                'data-max-size': '10485760'  # 10MB in bytes
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Add any additional notes about the delivery...'
            })
        }

    def clean_receipt_photo(self):
        photo = self.cleaned_data.get('receipt_photo')
        if photo:
            if photo.size > 5242880:  # 5MB limit
                raise forms.ValidationError('File size must be under 5MB.')
            return photo
        return None

    def clean_delivery_confirmation_file(self):
        file = self.cleaned_data.get('delivery_confirmation_file')
        if file:
            if file.size > 10485760:  # 10MB limit
                raise forms.ValidationError('File size must be under 10MB.')
            return file
        return None

class DeliveryStatusForm(forms.Form):
    STATUS_CHOICES = [
        ('pending_delivery', 'Pending Delivery'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('verified', 'Verified'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': 'Add any notes about this status change'
        })
    )