from django.db import models
from django.contrib.auth.models import User
from inventory.models import InventoryItem
import uuid
from decimal import Decimal

class Sale(models.Model):
    transaction_id = models.CharField(max_length=50, unique=True)
    sale_date = models.DateTimeField(auto_now_add=True)
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='purchases')
    sold_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_returned = models.BooleanField(default=False)
    return_date = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = str(uuid.uuid4().hex[:8].upper())
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale {self.transaction_id} - {self.sale_date.strftime('%Y-%m-%d %H:%M')}"

    @property
    def items_count(self):
        return self.items.count()

    @property
    def total_items_quantity(self):
        return sum(item.quantity for item in self.items.all())

class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, related_name='items', on_delete=models.CASCADE)
    item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True)
    quantity = models.PositiveIntegerField()
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.item.item_name if self.item else 'Unknown Item'}"

    @property
    def total_price(self):
        return self.quantity * self.price_per_unit

class ReturnItem(models.Model):
    sale_item = models.ForeignKey(SaleItem, related_name='returns', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    return_date = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(null=True, blank=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        # Check if return quantity is valid
        total_returned = self.sale_item.returns.aggregate(
            total=models.Sum('quantity'))['total'] or 0
        if total_returned + self.quantity > self.sale_item.quantity:
            raise ValidationError('Cannot return more items than were sold')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Update inventory
        if self.sale_item.item:
            self.sale_item.item.stock += self.quantity
            self.sale_item.item.save()
            
        # Check if all items in the sale are returned
        sale = self.sale_item.sale
        all_sale_items = sale.items.all()
        all_returned = all(
            item.returns.aggregate(
                total=models.Sum('quantity'))['total'] or 0 == item.quantity
            for item in all_sale_items
        )
        if all_returned:
            sale.is_returned = True
            sale.return_date = self.return_date
            sale.save()

    def __str__(self):
        return f"Return of {self.quantity}x {self.sale_item}"