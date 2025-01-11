from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    is_main = models.BooleanField(default=False)
    users = models.ManyToManyField(User, related_name='warehouses')

    def __str__(self):
        return self.name

class Brand(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class GlobalSettings(models.Model):
    reorder_level = models.PositiveIntegerField(default=10)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Global Settings'
        verbose_name_plural = 'Global Settings'

class InventoryItem(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, default=1)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    model = models.CharField(max_length=100)
    item_name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    stock = models.PositiveIntegerField()
    availability = models.BooleanField(default=True)
    image = models.ImageField(upload_to='inventory_images/', null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.brand} {self.model} - {self.item_name}"

    @property
    def needs_reorder(self):
        global_settings = GlobalSettings.objects.first()
        if not global_settings:
            global_settings = GlobalSettings.objects.create()
        return self.stock <= global_settings.reorder_level

    class Meta:
        ordering = ['brand', 'model', 'item_name']

    @classmethod
    def get_inventory_item_in_warehouse(cls, item, warehouse):
        try:
            return cls.objects.get(
                warehouse=warehouse,
                item_name=item.item_name,
                brand=item.brand,
                model=item.model
            )
        except cls.DoesNotExist:
            return None

class PendingPOItem(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='inventory_pending_items')
    item = models.ForeignKey('requisition.RequisitionItem', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.brand.name} - {self.item.item.item_name} ({self.quantity})"

    class Meta:
        ordering = ['brand', 'created_at']