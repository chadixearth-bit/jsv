from django import forms
from .models import InventoryItem, Brand, Category, Warehouse, GlobalSettings

class InventoryItemForm(forms.ModelForm):
    brand = forms.ModelChoiceField(queryset=Brand.objects.all(), empty_label="Select a brand")
    category = forms.ModelChoiceField(queryset=Category.objects.all(), empty_label="Select a category")

    class Meta:
        model = InventoryItem
        fields = ['brand', 'category', 'model', 'item_name', 'price', 'image', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Remove warehouse-related logic since we're creating items for all warehouses

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