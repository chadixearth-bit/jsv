from django import forms
from .models import Sale, SaleItem
from inventory.models import InventoryItem
from django.db.models import Q

class SaleItemForm(forms.ModelForm):
    class Meta:
        model = SaleItem
        fields = ['item', 'quantity']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantity'].widget.attrs.update({
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'min': '1'
        })

class SaleForm(forms.ModelForm):
    buyer_name = forms.CharField(max_length=100, required=True)
    buyer_contact = forms.CharField(max_length=50, required=True)
    search_query = forms.CharField(required=False)

    class Meta:
        model = Sale
        fields = []  # We'll handle items separately

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        search_query = kwargs.pop('search_query', None)
        super().__init__(*args, **kwargs)
        
        # Add classes to form fields
        self.fields['buyer_name'].widget.attrs.update({
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': "Enter buyer's name"
        })
        self.fields['buyer_contact'].widget.attrs.update({
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'placeholder': "Enter buyer's contact number"
        })
        
        if user:
            queryset = InventoryItem.objects.filter(warehouse__in=user.warehouses.all(), stock__gt=0)
            if search_query:
                queryset = queryset.filter(
                    Q(item_name__icontains=search_query) |
                    Q(brand__name__icontains=search_query) |
                    Q(category__name__icontains=search_query)
                )
            self.items_queryset = queryset