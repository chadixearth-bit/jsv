from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Warehouse

@receiver(post_save, sender=User)
def assign_default_warehouse(sender, instance, created, **kwargs):
    if created:
        default_warehouse = Warehouse.objects.filter(is_main=False).first()
        if default_warehouse:
            instance.warehouses.add(default_warehouse)