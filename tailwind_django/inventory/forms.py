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

    class Meta:
        model = InventoryItem
        fields = ['brand', 'category', 'model', 'item_name', 'price', 'image', 'description']
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
            'image': forms.FileInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'accept': 'image/*'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Enter item description'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make fields required
        self.fields['brand'].required = True
        self.fields['category'].required = True
        self.fields['model'].required = True
        self.fields['item_name'].required = True
        self.fields['price'].required = True
        
        # Add help text
        self.fields['image'].help_text = 'Upload an image of the item (optional)'
        self.fields['description'].help_text = 'Provide a detailed description of the item (optional)'

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