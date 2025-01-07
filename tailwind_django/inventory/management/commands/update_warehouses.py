from django.core.management.base import BaseCommand
from inventory.models import InventoryItem, Warehouse

class Command(BaseCommand):
    help = 'Updates inventory items with correct warehouses'

    def handle(self, *args, **kwargs):
        # Get the warehouses
        attendant_warehouse = Warehouse.objects.get(name='Attendant Warehouse')
        manager_warehouse = Warehouse.objects.get(name='Manager Warehouse')
        
        # Update items without a warehouse to use attendant warehouse by default
        items_updated = InventoryItem.objects.filter(
            warehouse__isnull=True
        ).update(warehouse=attendant_warehouse)
        self.stdout.write(self.style.SUCCESS(f"Updated {items_updated} items to Attendant Warehouse"))
