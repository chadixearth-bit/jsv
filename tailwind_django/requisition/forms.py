from django import forms
from .models import Requisition, RequisitionItem
from inventory.models import Warehouse, InventoryItem
from django.db.models import Q, Case, When, F, Value, IntegerField
import json

class RequisitionForm(forms.ModelForm):
    items = forms.ModelMultipleChoiceField(
        queryset=InventoryItem.objects.all(),
        required=True,
        widget=forms.SelectMultiple(attrs={'class': 'hidden'})
    )
    quantities = forms.CharField(
        required=True,
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
            print("\n=== DEBUG: RequisitionForm Init ===")
            print(f"User: {self.user.username}")
            print(f"Role: {self.user.customuser.role}")
            print(f"User Warehouse: {user_warehouse.name if user_warehouse else None}")
            
            if user_warehouse:
                # Show items based on user's warehouse
                queryset = InventoryItem.objects.filter(
                    warehouse=user_warehouse,
                    stock__gt=0  # Only show items with stock > 0
                ).select_related('brand', 'category', 'warehouse')
                
                print(f"Number of items in queryset: {queryset.count()}")
                for item in queryset:
                    print(f"Item: {item.item_name}, Brand: {item.brand.name}, Stock: {item.stock}, Warehouse: {item.warehouse.name}")
                self.fields['items'].queryset = queryset
            else:
                print("No warehouse found for user")
                self.fields['items'].queryset = InventoryItem.objects.none()
        
        # Add help text and labels
        self.fields['items'].help_text = "Select items from inventory"
        self.fields['reason'].help_text = "Provide a reason for this request"
        self.fields['reason'].label = "Reason"

    def clean(self):
        cleaned_data = super().clean()
        items = cleaned_data.get('items')
        quantities_json = cleaned_data.get('quantities')
        reason = cleaned_data.get('reason')

        if not items:
            raise forms.ValidationError("You must select at least one item.")
            
        if not reason:
            raise forms.ValidationError("Please provide a reason for this requisition.")

        try:
            quantities = json.loads(quantities_json or '{}')
            for item in items:
                quantity = int(quantities.get(str(item.id), 0))
                if quantity <= 0:
                    raise forms.ValidationError(f"Invalid quantity for item {item.item_name}")
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid quantities format")
        except (TypeError, ValueError):
            raise forms.ValidationError("Invalid quantity value")

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