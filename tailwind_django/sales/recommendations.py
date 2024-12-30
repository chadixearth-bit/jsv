from collections import defaultdict
from .models import Sale, SaleItem
from django.db.models import Count
from inventory.models import InventoryItem

def get_product_recommendations(item_id, min_support=0.01):
    """
    Get product recommendations based on what other customers bought together.
    
    Args:
        item_id: The ID of the current item
        min_support: Minimum support threshold (default 1%)
    
    Returns:
        List of recommended items with their confidence scores
    """
    # Get all sales that include the target item
    target_sales = Sale.objects.filter(items__item_id=item_id)
    
    # Count how many times each other item appears with our target item
    co_occurrences = defaultdict(int)
    total_target_sales = target_sales.count()
    
    if total_target_sales == 0:
        return []
    
    for sale in target_sales:
        # Get other items in the same sale
        other_items = sale.items.exclude(item_id=item_id)
        for sale_item in other_items:
            co_occurrences[sale_item.item_id] += 1
    
    # Calculate confidence scores
    recommendations = []
    for other_item_id, count in co_occurrences.items():
        try:
            item = InventoryItem.objects.get(id=other_item_id)
            confidence = count / total_target_sales
            if confidence >= min_support:
                recommendations.append({
                    'item': item,
                    'confidence': confidence,
                    'count': count
                })
        except InventoryItem.DoesNotExist:
            continue
    
    # Sort by confidence score
    recommendations.sort(key=lambda x: x['confidence'], reverse=True)
    return recommendations[:5]  # Return top 5 recommendations
