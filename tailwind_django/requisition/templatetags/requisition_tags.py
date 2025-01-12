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

@register.filter
def group_requisition_items(items):
    """
    Template filter to group requisition items by type (new vs existing)
    Usage: {{ requisition.items.all|group_requisition_items }}
    """
    new_items = []
    existing_items = []
    
    for item in items:
        if item.is_new_item:
            new_items.append(item)
        else:
            existing_items.append(item)
            
    return {
        'new_items': new_items,
        'existing_items': existing_items
    }
