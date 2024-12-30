from django.db import models
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from requisition.models import Requisition
from inventory.models import Warehouse

class CustomUser(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('attendant', 'Attendant'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    warehouses = models.ManyToManyField('inventory.Warehouse', related_name='custom_users')

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding  # Check if this is a new instance
        super().save(*args, **kwargs)
        
        if is_new:  # Only run this for new users
            from inventory.models import Warehouse
            
            # For admin role, assign all warehouses
            if self.role == 'admin':
                all_warehouses = Warehouse.objects.all()
                self.warehouses.add(*all_warehouses)
            
            # For manager and attendant roles
            elif self.role in ['manager', 'attendant']:
                warehouse_name = 'Manager Warehouse' if self.role == 'manager' else 'Warehouse Attendant'
                
                # Get or create the warehouse
                warehouse, created = Warehouse.objects.get_or_create(
                    name=warehouse_name,
                    defaults={'is_main': False}
                )
                
                # Assign warehouse to user
                self.warehouses.add(warehouse)

    def update_permissions(self):
        # Remove all existing permissions
        self.user.user_permissions.clear()

        # Add permissions based on role
        if self.role == 'manager':
            self.add_requisition_permission()
            # Add the can_approve_requisition permission
            content_type = ContentType.objects.get_for_model(Requisition)
            permission = Permission.objects.get(
                codename='can_approve_requisition',
                content_type=content_type,
            )
            self.user.user_permissions.add(permission)

        if self.role == 'admin':
            self.add_admin_permissions()
            # Remove requisition permissions for admin
            content_type = ContentType.objects.get_for_model(Requisition)
            requisition_permissions = Permission.objects.filter(
                content_type=content_type,
                codename__in=['add_requisition', 'change_requisition', 'delete_requisition']
            )
            self.user.user_permissions.remove(*requisition_permissions)

    def add_requisition_permission(self):
        content_type = ContentType.objects.get_for_model(Requisition)
        permission, created = Permission.objects.get_or_create(
            codename='can_approve_requisition',
            name='Can approve requisition',
            content_type=content_type,
        )
        self.user.user_permissions.add(permission)

    def add_admin_permissions(self):
        # Add all permissions for admin role
        all_permissions = Permission.objects.all()
        self.user.user_permissions.add(*all_permissions)

    @property
    def is_manager(self):
        return self.role == 'manager'

    @property
    def is_admin(self):
        return self.role == 'admin'