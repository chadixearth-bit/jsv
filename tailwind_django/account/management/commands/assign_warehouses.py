from django.core.management.base import BaseCommand
from account.models import CustomUser
from inventory.models import Warehouse

class Command(BaseCommand):
    help = 'Assigns warehouses to users based on their roles'

    def handle(self, *args, **kwargs):
        # Create warehouses if they don't exist
        attendant_warehouse, _ = Warehouse.objects.get_or_create(name='Attendant Warehouse')
        manager_warehouse, _ = Warehouse.objects.get_or_create(name='Manager Warehouse')
        
        # Get all users
        custom_users = CustomUser.objects.all()
        
        for custom_user in custom_users:
            # Clear existing warehouse assignments
            custom_user.warehouses.clear()
            
            # Assign warehouses based on role
            if custom_user.role == 'admin':
                custom_user.warehouses.add(attendant_warehouse, manager_warehouse)
            elif custom_user.role == 'attendant':
                custom_user.warehouses.add(attendant_warehouse)
            elif custom_user.role == 'manager':
                custom_user.warehouses.add(manager_warehouse)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully assigned warehouses to {custom_user.user.username}'))
