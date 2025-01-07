from django.core.management.base import BaseCommand
from inventory.models import InventoryItem, Warehouse

class Command(BaseCommand):
    help = 'Checks inventory items in each warehouse'

    def handle(self, *args, **kwargs):
        warehouses = Warehouse.objects.all()
        
        for warehouse in warehouses:
            items = InventoryItem.objects.filter(warehouse=warehouse)
            self.stdout.write(f"\nWarehouse: {warehouse.name}")
            self.stdout.write("-" * 50)
            
            if items.exists():
                for item in items:
                    self.stdout.write(f"- {item.item_name} (Stock: {item.stock})")
            else:
                self.stdout.write("No items in this warehouse")
