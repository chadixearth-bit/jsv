from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from inventory.models import InventoryItem, Warehouse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from model_utils import FieldTracker
from django.core.validators import RegexValidator

class RequisitionItem(models.Model):
    requisition = models.ForeignKey('Requisition', on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE)
    selected_source_item = models.ForeignKey('inventory.InventoryItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='source_requisition_items')
    quantity = models.PositiveIntegerField(default=1)
    delivered_quantity = models.PositiveIntegerField(null=True, blank=True)
    is_new_item = models.BooleanField(default=False, help_text="Indicates if this is a request for a new item not in inventory")

    def __str__(self):
        return f"{self.item.item_name} - {self.quantity} units"

class Requisition(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('pending_admin_approval', 'Pending Admin Approval'),
        ('approved_by_admin', 'Approved by Admin'),
        ('approved', 'Approved'),
        ('partially_approved', 'Partially Approved'),
        ('forwarded_to_admin', 'Forwarded to Admin'),
        ('rejected', 'Rejected'),
        ('pending_delivery', 'Pending Delivery'),
        ('in_delivery', 'In Delivery'),
        ('received', 'Received'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('pending_po', 'Pending Purchase Order'),
    ]
    
    REQUEST_TYPE_CHOICES = [
        ('item', 'Item Request'),
        ('labor_service', 'Labor/Service Request'),
    ]

    requester = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requisitions')
    reason = models.TextField()
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPE_CHOICES, default='item')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    source_warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE, related_name='source_requisitions', null=True, blank=True)
    destination_warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE, related_name='destination_requisitions', null=True, blank=True)
    manager_comment = models.TextField(null=True, blank=True)
    approval_comment = models.TextField(null=True, blank=True)
    delivery_image = models.ImageField(upload_to='delivery_images/', null=True, blank=True)
    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    received_date = models.DateTimeField(null=True, blank=True)
    delivery_comment = models.TextField(null=True, blank=True)
    tracker = FieldTracker()

    class Meta:
        permissions = [
            ("can_approve_requisition", "Can approve requisition"),
        ]

    def start_delivery(self, estimated_date, comment=None, delivered_qty=None):
        if self.status in ['approved', 'pending_delivery']:
            self.status = 'in_delivery'
            self.estimated_delivery_date = estimated_date
            self.delivery_comment = comment
            
            # Update delivered quantity for the requisition item
            if delivered_qty is not None:
                requisition_item = self.items.first()
                if requisition_item:
                    requisition_item.delivered_quantity = delivered_qty
                    requisition_item.save()
            
            self.save()

    def confirm_delivery(self):
        if self.status in ['in_delivery', 'pending_delivery']:
            self.status = 'received'
            self.received_date = timezone.now()
            self.save()

            # Update inventory quantities
            for item in self.items.all():
                delivered_qty = item.delivered_quantity or item.quantity

                # Deduct from source warehouse (manager's warehouse where items come from)
                source_item = InventoryItem.objects.filter(
                    item_name=item.item.item_name,
                    brand=item.item.brand,
                    category=item.item.category,
                    model=item.item.model,
                    warehouse=self.source_warehouse
                ).first()
                
                if source_item:
                    source_item.stock -= delivered_qty
                    source_item.save()
                    print(f"DEBUG: Deducted {delivered_qty} from source warehouse {self.source_warehouse.name}")

                # Add to destination warehouse (attendant's warehouse where items go to)
                dest_item = InventoryItem.objects.filter(
                    item_name=item.item.item_name,
                    brand=item.item.brand,
                    category=item.item.category,
                    model=item.item.model,
                    warehouse=self.destination_warehouse
                ).first()
                
                if dest_item:
                    dest_item.stock += delivered_qty
                    dest_item.save()
                    print(f"DEBUG: Added {delivered_qty} to destination warehouse {self.destination_warehouse.name}")
                else:
                    # Create new item in destination warehouse with delivered quantity
                    new_item = InventoryItem.objects.create(
                        item_name=item.item.item_name,
                        brand=item.item.brand,
                        category=item.item.category,
                        model=item.item.model,
                        warehouse=self.destination_warehouse,
                        stock=delivered_qty,
                        price=item.item.price
                    )
                    print(f"DEBUG: Created new item in destination warehouse {self.destination_warehouse.name} with {delivered_qty} stock")

    def update_inventory(self):
        for item in self.items.all():
            # Deduct from source warehouse
            if self.source_warehouse and item.selected_source_item:
                source_item = item.selected_source_item
                if source_item.warehouse == self.source_warehouse:
                    source_item.stock -= item.quantity
                    source_item.save()

            # Add to destination warehouse
            if self.destination_warehouse:
                # Check if item exists in destination warehouse
                dest_item = InventoryItem.objects.filter(
                    item_name=item.item.item_name,
                    warehouse=self.destination_warehouse
                ).first()
                
                if dest_item:
                    dest_item.stock += item.quantity
                    dest_item.save()
                else:
                    # Create new item in destination warehouse
                    new_item = InventoryItem.objects.create(
                        brand=item.item.brand,
                        category=item.item.category,
                        model=item.item.model,
                        item_name=item.item.item_name,
                        price=item.item.price,
                        stock=item.quantity,
                        warehouse=self.destination_warehouse,
                        description=item.item.description
                    )

    def check_quantity_availability(self):
        for requisition_item in self.items.all():
            if not requisition_item.selected_source_item or \
               requisition_item.selected_source_item.stock < requisition_item.quantity:
                return False
        return True if self.items.exists() else False

    def approve(self, user, comment=None):
        user_role = user.customuser.role if hasattr(user, 'customuser') else None
        
        if user_role == 'admin' and self.status == 'pending':
            self.status = 'approved_by_admin'
            self.manager_comment = comment
            self.save()
            
            # Create a purchase order automatically
            from purchasing.models import PurchaseOrder, PurchaseOrderItem
            from django.utils import timezone
            from datetime import timedelta
            
            # Create the purchase order
            po = PurchaseOrder.objects.create(
                created_by=user,
                status='draft',
                order_date=timezone.now().date(),
                expected_delivery_date=timezone.now().date() + timedelta(days=7),
                notes=f"Auto-generated from requisition #{self.id}"
            )
            
            # Add requisition items to the purchase order
            for req_item in self.items.all():
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    item=req_item.item,
                    brand=req_item.item.brand,
                    model_name=req_item.item.model,
                    quantity=req_item.quantity,
                    unit_price=req_item.item.price,
                    subtotal=req_item.item.price * req_item.quantity
                )
            
            # Calculate total amount
            po.calculate_total()
            
            # Link requisition to purchase order
            po.requisitions.add(self)
            
            # Update status to pending_delivery
            self.status = 'pending_delivery'
            self.save()
        elif user_role == 'manager' and self.status == 'pending':
            if not self.check_quantity_availability():
                raise ValueError("Insufficient quantity available in the source warehouse.")
            
            self.status = 'pending_delivery'
            self.manager_comment = comment
            self.save()
        else:
            raise ValueError("Invalid approval attempt")

    def reject(self, user, comment=None):
        user_role = user.customuser.role if hasattr(user, 'customuser') else None
        
        if user_role == 'manager' and self.status == 'pending':
            self.status = 'rejected'
            self.manager_comment = comment
            self.save()
        else:
            raise ValueError("Invalid rejection attempt")

    def can_edit(self):
        return self.status == 'pending'

    def __str__(self):
        return f"Requisition {self.id} - Item Request by {self.requester.username}"

    def clean(self):
        from django.core.exceptions import ValidationError
        # Skip validation if we're creating a new requisition (no primary key yet)
        # or if we explicitly set the skip flag
        if hasattr(self, '_skip_item_validation'):
            return
        
        if self.pk and not self.items.all():
            raise ValidationError("Items are required for item requisitions.")

class RequisitionStatusHistory(models.Model):
    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=25, choices=Requisition.STATUS_CHOICES)
    comment = models.TextField(blank=True, null=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Requisition Status Histories"

    def __str__(self):
        return f"{self.requisition.id} - {self.get_status_display()} at {self.timestamp}"

@receiver(post_save, sender=Requisition)
def track_requisition_status(sender, instance, created, **kwargs):
    if created or instance.tracker.has_changed('status'):
        RequisitionStatusHistory.objects.create(
            requisition=instance,
            status=instance.status,
            comment=instance.manager_comment if instance.manager_comment else instance.approval_comment,
            changed_by=instance.requester if created else None  # We'll need to set this properly in views
        )

class Delivery(models.Model):
    STATUS_CHOICES = [
        ('pending_delivery', 'Pending Delivery'),
        ('in_delivery', 'In Delivery'),
        ('pending_manager', 'Pending Manager Confirmation'),  # After attendant uploads image
        ('pending_admin', 'Pending Admin Confirmation'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ]

    requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE)
    source_warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE, related_name='source_deliveries', null=True)
    destination_warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.CASCADE, related_name='destination_deliveries', null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_delivery')
    delivered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries_made')
    delivery_personnel_name = models.CharField(max_length=100, null=True, blank=True)
    delivery_personnel_phone = models.CharField(
        max_length=20, 
        null=True, 
        blank=True,
        validators=[
            RegexValidator(
                regex=r'^(63|09)\d{9}$',
                message='Phone number must be 11 digits and start with either "63" or "09"',
                code='invalid_phone'
            )
        ]
    )
    delivery_date = models.DateTimeField(null=True, blank=True)
    estimated_delivery_date = models.DateField(null=True, blank=True)
    delivery_image = models.ImageField(upload_to='delivery_images/', null=True, blank=True)  # Proof of delivery by attendant
    delivery_receipt = models.FileField(upload_to='delivery_receipts/', null=True, blank=True)
    additional_docs = models.FileField(upload_to='delivery_docs/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Deliveries"

    def __str__(self):
        return f"Delivery for Requisition #{self.requisition.id}"

class DeliveryItem(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey('inventory.InventoryItem', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Delivery.STATUS_CHOICES, default='pending_delivery')
    
    def __str__(self):
        return f"{self.quantity} x {self.item.item_name} for {self.delivery}"

    def save(self, *args, **kwargs):
        # Validate quantity before saving
        if self.quantity > self.item.stock:
            raise ValidationError(f'Insufficient stock for {self.item.item_name}. Available: {self.item.stock}')
        super().save(*args, **kwargs)

@receiver(post_save, sender=DeliveryItem)
def update_requisition_status(sender, instance, created, **kwargs):
    if created:
        delivery = instance.delivery
        requisition = delivery.requisition
        
        # Update requisition status if not already in delivery
        if requisition.status == 'pending_delivery':
            requisition.status = 'in_delivery'
            requisition.save()

@receiver(post_save, sender=Delivery)
def handle_delivery_status(sender, instance, created, **kwargs):
    if created:
        requisition = instance.requisition
        if requisition.status == 'pending_delivery':
            requisition.status = 'in_delivery'
            requisition.save()

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    requisition = models.ForeignKey('Requisition', on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']