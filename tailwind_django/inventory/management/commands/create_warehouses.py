from django.core.management.base import BaseCommand
from inventory.models import Warehouse

class Command(BaseCommand):
    help = 'Creates default warehouses if they do not exist'

    def handle(self, *args, **kwargs):
        warehouses = [
            {'name': 'Attendant Warehouse', 'is_main': False},
            {'name': 'Manager Warehouse', 'is_main': True},
        ]

        for warehouse_data in warehouses:
            warehouse, created = Warehouse.objects.get_or_create(
                name=warehouse_data['name'],
                defaults={'is_main': warehouse_data['is_main']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Successfully created warehouse "{warehouse.name}"'))
            else:
                self.stdout.write(self.style.WARNING(f'Warehouse "{warehouse.name}" already exists'))
