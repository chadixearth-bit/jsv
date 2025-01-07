from django import forms
from .models import Requisition, RequisitionItem
from inventory.models import Warehouse, InventoryItem
from django.db.models import Q, Case, When, F, Value, IntegerField
import json

class RequisitionForm(forms.ModelForm):
    items = forms.ModelMultipleChoiceField(
        queryset=InventoryItem.objects.all(),
        required=False,  # Make items optional
        widget=forms.SelectMultiple(attrs={'class': 'hidden'})
    )
    quantities = forms.CharField(
        required=False,  # Make quantities optional
        widget=forms.HiddenInput(),
        help_text="JSON string of quantities for each item"
    )
    
    class Meta:
        model = Requisition
        fields = ['request_type', 'reason']
        widgets = {
            'request_type': forms.HiddenInput(),
            'reason': forms.Textarea(attrs={
                'rows': 4, 
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm',
                'placeholder': ' Enter the reason for this requisition...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default request type
        self.fields['request_type'].initial = 'item'
        
        if self.user and hasattr(self.user, 'customuser'):
            user_warehouse = self.user.customuser.warehouses.first()
            if user_warehouse:
                # Show items based on user's warehouse, including those with 0 stock
                queryset = InventoryItem.objects.filter(
                    warehouse=user_warehouse
                ).select_related('brand', 'category', 'warehouse')
                
                self.fields['items'].queryset = queryset

    def clean(self):
        cleaned_data = super().clean()
        items = cleaned_data.get('items', [])
        new_items_json = self.data.get('new_items')
        reason = cleaned_data.get('reason')
        
        if not reason:
            raise forms.ValidationError("Please provide a reason for this requisition.")
        
        # Check if we have either items or new items
        has_items = bool(items)
        has_new_items = bool(new_items_json)
        
        if not has_items and not has_new_items:
            raise forms.ValidationError("You must select at least one item or request a new item.")
        
        # If we have existing items, validate their quantities
        if has_items:
            quantities = self.data.get('quantities', '{}')

            try:
                quantities_dict = json.loads(quantities)
            except json.JSONDecodeError:
                raise forms.ValidationError("Invalid quantities format")

            # Only validate stock levels if the user is not an attendant
            if hasattr(self.user, 'customuser') and self.user.customuser.role != 'attendant':
                for item in items:
                    quantity = int(quantities_dict.get(str(item.id), 0))
                    if quantity > item.stock:
                        raise forms.ValidationError(
                            f"Requested quantity ({quantity}) exceeds available stock ({item.stock}) for {item.item_name}."
                        )
        
        return cleaned_data

class RequisitionApprovalForm(forms.Form):
    DECISION_CHOICES = [
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]
    decision = forms.ChoiceField(
        choices=DECISION_CHOICES,
        required=True,
        widget=forms.HiddenInput()
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'shadow-sm focus:ring-indigo-500 focus:border-indigo-500 block w-full sm:text-sm border-gray-300 rounded-md',
            'rows': 3,
            'placeholder': 'Add any comments about this requisition...'
        }),
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.requisition = kwargs.pop('requisition', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        if not decision:
            raise forms.ValidationError("Please select a decision (approve or reject)")
        return cleaned_data

class DeliveryManagementForm(forms.Form):
    estimated_delivery_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
        }),
        required=True
    )
    delivery_comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
        }),
        required=False
    )
    delivered_quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm'
        }),
        required=True
    )

class DeliveryConfirmationForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ['delivery_image']