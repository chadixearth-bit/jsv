from django.core.management.base import BaseCommand
from inventory.models import Warehouse, InventoryItem
from django.db.models import Count

class Command(BaseCommand):
    help = 'Cleans up duplicate warehouses and shows warehouse statistics'

    def handle(self, *args, **kwargs):
        # Get all warehouses
        warehouses = Warehouse.objects.all()
        self.stdout.write("Current warehouses:")
        for warehouse in warehouses:
            item_count = InventoryItem.objects.filter(warehouse=warehouse).count()
            self.stdout.write(f"- {warehouse.name} (ID: {warehouse.id}, Items: {item_count}, Is Main: {warehouse.is_main})")

        # Find duplicates
        duplicates = (
            Warehouse.objects.values('name')
            .annotate(name_count=Count('id'))
            .filter(name_count__gt=1)
        )

        if duplicates:
            self.stdout.write("\nFound duplicate warehouses:")
            for duplicate in duplicates:
                name = duplicate['name']
                dupe_warehouses = Warehouse.objects.filter(name=name).order_by('id')
                self.stdout.write(f"\nDuplicates of {name}:")
                
                # Keep the first one (with lowest ID) and merge others into it
                keep_warehouse = dupe_warehouses.first()
                self.stdout.write(f"Keeping warehouse: {keep_warehouse.name} (ID: {keep_warehouse.id})")
                
                for dupe in dupe_warehouses[1:]:
                    self.stdout.write(f"Merging and deleting: {dupe.name} (ID: {dupe.id})")
                    # Update all items from duplicate warehouse to the kept warehouse
                    InventoryItem.objects.filter(warehouse=dupe).update(warehouse=keep_warehouse)
                    # Delete the duplicate warehouse
                    dupe.delete()
        else:
            self.stdout.write("\nNo duplicate warehouses found.")
