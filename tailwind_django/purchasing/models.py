from django.db import models
from django.contrib.auth.models import User
from inventory.models import InventoryItem, Warehouse
from decimal import Decimal
from django.conf import settings

class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.name)

class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_supplier', 'Pending Supplier Approval'),
        ('supplier_accepted', 'Accepted by Supplier'),
        ('supplier_rejected', 'Rejected by Supplier'),
        ('confirmed', 'Confirmed'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ]

    po_number = models.CharField(max_length=20, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='purchase_orders')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='purchase_orders')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchase_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    order_date = models.DateField()
    expected_delivery_date = models.DateField()
    actual_delivery_date = models.DateField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    delivery_verification_file = models.FileField(upload_to='delivery_verifications/', null=True, blank=True)
    delivery_verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_deliveries')
    delivery_verification_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    requisitions = models.ManyToManyField('requisition.Requisition', blank=True, related_name='purchase_orders')

    def calculate_total(self) -> None:
        from decimal import Decimal
        total = sum((Decimal(item.subtotal) for item in self.items.all()), Decimal('0'))
        self.total_amount = total
        self.save()

    def link_requisitions(self) -> None:
        """Link this purchase order with relevant requisitions"""
        from requisition.models import Requisition
        
        po_items = self.items.all()
        for po_item in po_items:
            matching_requisitions = Requisition.objects.filter(
                request_type='item',
                status='approved_by_admin',
                item=po_item.item,
                item__stock=0
            )
            self.requisitions.add(*matching_requisitions)

    def save(self, *args, **kwargs) -> None:
        if not self.po_number:
            last_po = PurchaseOrder.objects.order_by('-id').first()
            if last_po and last_po.po_number and last_po.po_number[2:].isdigit():
                last_number = int(last_po.po_number[2:])
                self.po_number = f'PO{str(last_number + 1).zfill(6)}'
            else:
                self.po_number = 'PO000001'
        super().save(*args, **kwargs)

    def can_change_status(self, user, new_status: str) -> bool:
        """Check if user can change PO to the new status"""
        role = user.customuser.role
        current_status = self.status

        # Admin can change any status
        if role == 'admin':
            return True

        # Supplier-related status changes
        if role == 'supplier':
            if current_status == 'pending_supplier':
                return new_status in ['supplier_accepted', 'supplier_rejected']
            return False

        # Warehouse manager can verify delivery
        if role == 'manager':
            if current_status in ['in_transit', 'delivered']:
                return new_status in ['delivered', 'completed']
            return False

        # Warehouse attendant can mark as delivered
        if role == 'attendant':
            if current_status == 'in_transit':
                return new_status == 'delivered'
            return False

        return False

    def __str__(self) -> str:
        return f"PO-{self.po_number}"

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def save(self, *args, **kwargs) -> None:
        # Ensure quantity is an integer and unit_price is Decimal
        self.quantity = int(str(self.quantity or 0))
        if isinstance(self.unit_price, (int, float, str, Decimal)):
            self.unit_price = Decimal(str(self.unit_price))
        # Calculate subtotal
        self.subtotal = Decimal(str(self.quantity)) * Decimal(str(self.unit_price))
        super().save(*args, **kwargs)
        # Update purchase order total
        if self.purchase_order:
            self.purchase_order.calculate_total()

    def __str__(self) -> str:
        return f"{self.item.item_name} - {self.quantity} units"

class Delivery(models.Model):
    STATUS_CHOICES = [
        ('pending_delivery', 'Pending Delivery'),
        ('pending_confirmation', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ]
    
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='deliveries')
    delivery_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending_delivery')
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_deliveries')
    received_date = models.DateTimeField(null=True, blank=True)
    delivery_image = models.ImageField(upload_to='delivery_images/%Y/%m/%d/', null=True, blank=True)
    delivery_note = models.TextField(null=True, blank=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='confirmed_deliveries')
    confirmed_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Deliveries'

    def __str__(self):
        return f"Delivery for {self.purchase_order.po_number}"

    @property
    def estimated_delivery_date(self):
        return self.purchase_order.expected_delivery_date

class DeliveryItem(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='items')
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE)
    quantity_delivered = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.purchase_order_item.item.item_name} - {self.quantity_delivered} units"

    class Meta:
        ordering = ['id']