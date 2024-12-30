from django import template
from inventory.models import InventoryItem

register = template.Library()

@register.filter
def get_inventory_item(item, warehouse):
    """
    Template filter to get an inventory item in a specific warehouse
    Usage: {{ item|get_inventory_item:warehouse }}
    """
    try:
        return InventoryItem.objects.get(
            warehouse=warehouse,
            item_name=item.item_name,
            brand=item.brand,
            model=item.model
        )
    except InventoryItem.DoesNotExist:
        return None
