from django.core.management.base import BaseCommand
from inventory.models import InventoryItem, Warehouse, Brand
from django.db import transaction

def add_sample_items():
    try:
        with transaction.atomic():
            # Get or create the attendant warehouse
            attendant_warehouse = Warehouse.objects.get(name='Attendant Warehouse')
            
            # Get or create a sample brand
            brand, _ = Brand.objects.get_or_create(name='Sample Brand')
            
            # Create sample items
            sample_items = [
                {
                    'item_name': 'Sample Laptop',
                    'stock': 10,
                    'model': 'Model X1',
                    'price': 999.99,
                    'description': 'High-performance laptop for testing'
                },
                {
                    'item_name': 'Sample Monitor',
                    'stock': 5,
                    'model': 'Display Pro',
                    'price': 299.99,
                    'description': 'Professional grade monitor'
                },
                {
                    'item_name': 'Sample Keyboard',
                    'stock': 15,
                    'model': 'KB-2023',
                    'price': 79.99,
                    'description': 'Mechanical gaming keyboard'
                }
            ]
            
            created_items = []
            for item_data in sample_items:
                item = InventoryItem.objects.create(
                    warehouse=attendant_warehouse,
                    brand=brand,
                    **item_data
                )
                created_items.append(item)
                print(f"Created item: {item.item_name}")
            
            return created_items
    except Exception as e:
        print(f"Error creating sample items: {str(e)}")
        return None

if __name__ == '__main__':
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tailwind_django.settings')
    django.setup()
    
    print("Adding sample items...")
    created_items = add_sample_items()
    if created_items:
        print("\nSuccessfully added sample items:")
        for item in created_items:
            print(f"- {item.item_name} (Stock: {item.stock})")
    else:
        print("Failed to add sample items")
