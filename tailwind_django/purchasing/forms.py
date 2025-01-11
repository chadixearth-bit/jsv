from django import forms
from django.db.models.query import QuerySet
from typing import Any
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, Delivery
from inventory.models import InventoryItem, Warehouse
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

class PurchaseOrderItemForm(forms.ModelForm):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Type hint for queryset to help type checker
        self.fields['item'].queryset = InventoryItem.objects.filter(availability=True)  # type: ignore
        self.fields['item'].label_from_instance = lambda obj: f"{obj.item_name} ({obj.item_code})"
        self.fields['item'].required = False  # Make item field optional for new items

    def clean(self) -> dict:
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        item = cleaned_data.get('item')
        brand = cleaned_data.get('brand', '').strip()  # Add strip() to remove whitespace
        model_name = cleaned_data.get('model_name')

        # Validate brand field
        if not brand:
            raise forms.ValidationError("Brand is required")

        # Validate required fields for new items
        if not item and not model_name:
            raise forms.ValidationError("For new items, model name is required")

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

class PurchaseOrderForm(forms.ModelForm):
    verification_file = forms.FileField(required=False, widget=forms.FileInput(attrs={
        'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
        'accept': 'image/*,.pdf'
    }))
    
    items = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'warehouse', 'order_date', 'expected_delivery_date', 'notes', 'verification_file']
        widgets = {
            'supplier': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'required': True
            }),
            'warehouse': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'required': True
            }),
            'order_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'required': True
            }),
            'expected_delivery_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'required': True
            }),
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Add any additional notes about this purchase order...'
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        initial = kwargs.get('initial', {})
        super().__init__(*args, **kwargs)
        self.user = user
        
        # Initialize supplier and warehouse querysets
        self.fields['supplier'].queryset = Supplier.objects.all()
        self.fields['warehouse'].queryset = Warehouse.objects.filter(
            name__in=['Attendant Warehouse', 'Manager Warehouse']
        )
        
        print("Initial data in form init:", initial)  # Debug print
        
        # Set initial values from session if available and not already set
        if user and hasattr(user, 'session') and 'po_draft_data' in user.session:
            po_data = user.session.get('po_draft_data', {})
            if po_data:
                # Only update fields that aren't already set
                for field in ['supplier', 'warehouse', 'expected_delivery_date', 'notes']:
                    if field not in initial:
                        self.initial[field] = po_data.get(field)
        
        print("Final form initial data:", self.initial)  # Debug print

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('expected_delivery_date') and cleaned_data.get('order_date'):
            if cleaned_data['expected_delivery_date'] < cleaned_data['order_date']:
                raise forms.ValidationError("Expected delivery date cannot be earlier than the order date.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            
            # Process items data if available
            if hasattr(self, 'cleaned_data') and 'items' in self.cleaned_data:
                items_data = self.cleaned_data['items']
                if isinstance(items_data, str):
                    try:
                        items_data = json.loads(items_data)
                    except json.JSONDecodeError:
                        items_data = []
                
                for item_data in items_data:
                    PurchaseOrderItem.objects.create(
                        purchase_order=instance,
                        brand=item_data['brand'],
                        item_name=item_data['item_name'],
                        model_name=item_data['model'],
                        quantity=int(item_data['quantity']),
                        unit_price=float(item_data['unit_price'])
                    )
                
                # Calculate total amount
                instance.calculate_total()
        
        return instance

class DeliveryReceiptForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ['delivery_image', 'delivery_note']
        widgets = {
            'delivery_image': forms.FileInput(attrs={
                'class': 'py-2 px-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 block w-full text-sm',
                'accept': 'image/*'
            }),
            'delivery_note': forms.Textarea(attrs={
                'class': 'shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border border-gray-300 rounded-md',
                'rows': 3,
                'placeholder': 'Add any notes about the delivery...'
            })
        }

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