from django import forms
from .models import Requisition
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
    
    # Add filter for stock level
    stock_filter = forms.ChoiceField(
        choices=[
            ('all', 'All Items'),
            ('low', 'Low Stock First'),
            ('out', 'Out of Stock'),
        ],
        required=False,
        initial='low',
        widget=forms.Select(attrs={'class': 'form-select mb-2'})
    )

    class Meta:
        model = Requisition
        fields = ['request_type', 'reason']
        widgets = {
            'request_type': forms.Select(attrs={
                'class': 'form-select',
            }),
            'reason': forms.Textarea(attrs={'rows': 4, 'class': 'form-textarea'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and hasattr(self.user, 'customuser'):
            user_warehouse = self.user.customuser.warehouses.first()
            
            # For attendants, show warehouses they can request from
            if self.user.customuser.role == 'attendant':
                # Get all warehouses that have managers assigned, regardless of stock
                manager_warehouses = Warehouse.objects.filter(
                    custom_users__role='manager'  # Get warehouses with managers
                ).exclude(
                    id=user_warehouse.id if user_warehouse else None  # Exclude attendant's own warehouse
                ).distinct()
                
                if not manager_warehouses.exists():
                    # If no manager warehouses found, show a message
                    self.fields['source_warehouse'] = forms.ModelChoiceField(
                        queryset=Warehouse.objects.none(),
                        widget=forms.Select(attrs={
                            'class': 'form-select',
                            'disabled': 'disabled'
                        })
                    )
                else:
                    self.fields['source_warehouse'] = forms.ModelChoiceField(
                        queryset=manager_warehouses,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )
                
                # Always show items from attendant's warehouse
                base_queryset = InventoryItem.objects.filter(
                    warehouse=user_warehouse
                ).select_related('brand') if user_warehouse else InventoryItem.objects.none()
                
                # Apply stock level annotation
                base_queryset = base_queryset.annotate(
                    stock_status=Case(
                        When(stock=0, then=Value(0)),  # Out of stock
                        When(stock__lte=5, then=Value(1)),  # Low stock
                        default=Value(2),  # Normal stock
                        output_field=IntegerField(),
                    )
                ).order_by('stock_status', '-stock', 'item_name')
                
                self.fields['items'].queryset = base_queryset
                self.fields['items'].widget.attrs['class'] = 'form-select item-select'
            else:
                # For managers, show only items from their warehouse
                if user_warehouse:
                    # Managers don't need to select a warehouse since they can only request from their own
                    base_queryset = InventoryItem.objects.filter(
                        warehouse=user_warehouse
                    ).select_related('brand')
                    
                    # Apply stock level annotation with fixed threshold
                    base_queryset = base_queryset.annotate(
                        stock_status=Case(
                            When(stock=0, then=Value(0)),  # Out of stock
                            When(stock__lte=5, then=Value(1)),  # Low stock (threshold of 5)
                            default=Value(2),  # Normal stock
                            output_field=IntegerField(),
                        )
                    ).order_by('stock_status', '-stock', 'item_name')
                    
                    self.fields['items'].queryset = base_queryset
                else:
                    self.fields['items'].queryset = InventoryItem.objects.none()
        
        # Add help text and labels
        self.fields['items'].help_text = "Select items from inventory"
        self.fields['reason'].help_text = "Provide a reason for this request"

    def clean(self):
        cleaned_data = super().clean()
        items = cleaned_data.get('items')
        quantities_json = cleaned_data.get('quantities')
        
        if not items:
            raise forms.ValidationError("You must select at least one item.")
            
        # Skip stock validation if attendant is requesting from their own warehouse
        if self.user and hasattr(self.user, 'customuser') and self.user.customuser.role == 'attendant':
            user_warehouse = self.user.customuser.warehouses.first()
            if user_warehouse:
                # No need to validate stock for items from attendant's own warehouse
                return cleaned_data
        
        try:
            quantities = json.loads(quantities_json)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid quantities format")
        
        # Skip validation for managers since they only request for purchase orders
        if self.user and hasattr(self.user, 'customuser') and self.user.customuser.role == 'manager':
            return cleaned_data
            
        # For all other cases, validate stock levels
        for item_id, requested_quantity in quantities.items():
            item = InventoryItem.objects.filter(id=item_id).first()
            if item:
                if item.stock < requested_quantity:
                    raise forms.ValidationError(
                        f'Requested quantity ({requested_quantity}) exceeds available stock ({item.stock}) for {item.item_name}'
                    )
        return cleaned_data

    def clean_items(self):
        items = self.cleaned_data.get('items')
        if not items:
            self.add_error('items', 'Please select at least one item.')
        return items

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