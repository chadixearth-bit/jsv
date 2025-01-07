import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from inventory.models import InventoryItem, Warehouse

def update_warehouses():
    # Get the warehouses
    attendant_warehouse = Warehouse.objects.get(name='Attendant Warehouse')
    manager_warehouse = Warehouse.objects.get(name='Manager Warehouse')
    
    # Update items with attendant_warehouse location
    items_updated = InventoryItem.objects.filter(
        location='attendant_warehouse', 
        warehouse__isnull=True
    ).update(warehouse=attendant_warehouse)
    print(f"Updated {items_updated} items to Attendant Warehouse")
    
    # Update items with manager_warehouse location
    items_updated = InventoryItem.objects.filter(
        location='manager_warehouse', 
        warehouse__isnull=True
    ).update(warehouse=manager_warehouse)
    print(f"Updated {items_updated} items to Manager Warehouse")

if __name__ == '__main__':
    update_warehouses()
