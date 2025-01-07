from django import forms
from .models import InventoryItem, Brand, Category, Warehouse, GlobalSettings

class InventoryItemForm(forms.ModelForm):
    brand = forms.ModelChoiceField(
        queryset=Brand.objects.all(), 
        empty_label="Select a brand",
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'required': True
        })
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(), 
        empty_label="Select a category",
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'required': True
        })
    )
    warehouse = forms.ChoiceField(
        choices=[
            ('', 'Select a warehouse'),
            ('attendant_warehouse', 'Attendant Warehouse'),
            ('manager_warehouse', 'Manager Warehouse'),
            ('both_warehouses', 'Both Warehouses')
        ],
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            'required': True
        })
    )

    class Meta:
        model = InventoryItem
        fields = ['brand', 'category', 'warehouse', 'model', 'item_name', 'price', 'stock', 'image']
        widgets = {
            'model': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Enter model number or name'
            }),
            'item_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Enter item name'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'min': '0.01',
                'step': '0.01',
                'placeholder': 'Enter price'
            }),
            'stock': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'min': '0',
                'step': '1',
                'placeholder': 'Enter stock quantity'
            }),
            'image': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'accept': 'image/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['brand'].required = True
        self.fields['category'].required = True
        self.fields['model'].required = True
        self.fields['item_name'].required = True
        self.fields['price'].required = True
        self.fields['stock'].required = True
        self.fields['warehouse'].required = True
        
        # Add help text
        self.fields['image'].help_text = 'Upload an image of the item (optional)'
        
        # Filter warehouse choices based on user role
        if self.user and hasattr(self.user, 'customuser'):
            user_role = self.user.customuser.role
            if user_role == 'attendant':
                self.fields['warehouse'].choices = [
                    ('', 'Select a warehouse'),
                    ('attendant_warehouse', 'Attendant Warehouse'),
                    ('both_warehouses', 'Both Warehouses')
                ]
            elif user_role == 'manager':
                self.fields['warehouse'].choices = [
                    ('', 'Select a warehouse'),
                    ('manager_warehouse', 'Manager Warehouse'),
                    ('both_warehouses', 'Both Warehouses')
                ]

    def clean_warehouse(self):
        warehouse = self.cleaned_data.get('warehouse')
        if warehouse == 'both_warehouses':
            return warehouse
        return Warehouse.objects.get(pk=warehouse)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Skip saving the warehouse field if 'both_warehouses' is selected
        if self.cleaned_data['warehouse'] == 'both_warehouses':
            return instance
        instance.warehouse = self.cleaned_data['warehouse']
        if commit:
            instance.save()
        return instance

class GlobalSettingsForm(forms.ModelForm):
    class Meta:
        model = GlobalSettings
        fields = ['reorder_level']
        widgets = {
            'reorder_level': forms.NumberInput(attrs={
                'class': 'pl-3 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm',
                'min': '0'
            })
        }

class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name']

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']