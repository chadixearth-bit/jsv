from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.db.models.manager import Manager
from django.db.models import QuerySet
import json
from decimal import Decimal
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.template.loader import get_template
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from typing import Any, Dict, Optional, Type, Union

from requisition.models import Requisition
from inventory.models import InventoryItem, Brand, Warehouse, Category
from .models import PurchaseOrder, PurchaseOrderItem, Supplier, Delivery, DeliveryItem
from .forms import PurchaseOrderForm, PurchaseOrderItemForm, SupplierForm, DeliveryReceiptForm
from .utils import generate_purchase_order_pdf
from django.db.models import Q

# Type hints for Django models
PurchaseOrder.objects: Manager
Requisition.objects: Manager
InventoryItem.objects: Manager
Brand.objects: Manager
Delivery.objects: Manager
DeliveryItem.objects: Manager
PurchaseOrderItem.objects: Manager
Supplier.objects: Manager

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchasing/purchase_order_list.html'
    context_object_name = 'orders'

    def get_queryset(self) -> QuerySet[PurchaseOrder]:
        return PurchaseOrder.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add approved requisitions that don't have POs yet
        context['approved_requisitions'] = Requisition.objects.filter(
            status='approved_by_admin'
        ).exclude(
            purchase_orders__isnull=False
        ).order_by('-created_at')
        return context

class PurchaseOrderCreateView(LoginRequiredMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchasing/purchase_order_form.html'
    
    def dispatch(self, request, *args, **kwargs) -> Any:
        # Allow both superusers and admin users to create POs
        if request.user.is_superuser or (hasattr(request.user, 'customuser') and request.user.customuser.role == 'admin'):
            return super().dispatch(request, *args, **kwargs)
        messages.error(request, "Only admin users can create purchase orders.")
        return redirect('purchasing:list')

    def get_form_kwargs(self) -> Dict:
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict:
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Purchase Order'
        context['suppliers'] = Supplier.objects.all()
        context['warehouses'] = Warehouse.objects.filter(
            name__in=['Attendant Warehouse', 'Manager Warehouse']
        )
        context['pending_requisitions'] = Requisition.objects.filter(
            request_type='item',
            status='approved_by_admin',
            items__item__stock=0
        ).distinct()
        context['available_items'] = InventoryItem.objects.select_related(
            'brand', 
            'category'
        ).filter(
            availability=True
        ).order_by('brand__name', 'model', 'item_name')
        return context

    def form_valid(self, form: PurchaseOrderForm) -> Any:
        try:
            with transaction.atomic():
                po = form.save(commit=False)
                po.created_by = self.request.user
                po.status = 'pending_supplier'
                po.save()

                # Get items data from the form
                items_data = self.request.POST.get('items_data', '[]')
                items = json.loads(items_data)

                for item_data in items:
                    # Handle both existing and new items
                    if item_data.get('item_id'):
                        # Existing item
                        item = InventoryItem.objects.get(id=item_data['item_id'])
                    else:
                        # Create or get brand
                        brand, _ = Brand.objects.get_or_create(name=item_data['brand'])
                        
                        # Get or create a default category
                        category, _ = Category.objects.get_or_create(name='General')
                        
                        # Create new item with the item name from the form
                        item_name = item_data.get('itemName', f"{item_data['brand']} {item_data['model']}")
                        
                        # Create new item
                        item = InventoryItem.objects.create(
                            brand=brand,
                            category=category,
                            model=item_data['model'],
                            item_name=item_name,
                            price=Decimal(str(item_data['unitPrice'])),
                            stock=0,  # Initial stock is 0 until delivery
                            warehouse=po.warehouse,  # Assign to PO's warehouse
                            location='manager_warehouse' if po.warehouse.name == 'Manager Warehouse' else 'attendant_warehouse',
                            availability=True
                        )

                    # Create purchase order item
                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        item=item,
                        brand=item_data['brand'],
                        model_name=item_data['model'],
                        quantity=int(item_data['quantity']),
                        unit_price=Decimal(str(item_data['unitPrice']))
                    )

                messages.success(self.request, "Purchase order created successfully!")
                return redirect('purchasing:list')

        except Exception as e:
            print(f"Error creating purchase order: {str(e)}")
            messages.error(self.request, f"Error creating purchase order: {str(e)}")
            return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('purchasing:view_purchase_order', kwargs={'pk': self.object.pk})

class PurchaseOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchasing/purchase_order_form.html'
    success_url = reverse_lazy('purchasing:list')

    def dispatch(self, request, *args, **kwargs) -> Any:
        # Allow both superusers and admin users to update POs
        if request.user.is_superuser or (hasattr(request.user, 'customuser') and request.user.customuser.role == 'admin'):
            return super().dispatch(request, *args, **kwargs)
        messages.error(request, "Only admin users can update purchase orders.")
        return redirect('purchasing:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edit Purchase Order'
        context['is_edit'] = True
        context['purchase_order'] = self.get_object()
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                po = form.save(commit=False)
                po.created_by = self.request.user
                po.save()

                # Handle existing items updates
                existing_items = []
                items_to_delete = []
                
                # Get all item IDs from the form
                for key in self.request.POST:
                    if key.startswith('existing_items[]'):
                        item_id = self.request.POST.getlist(key)[0]
                        existing_items.append(item_id)
                
                # Update or delete existing items
                for item in po.items.all():
                    if str(item.id) not in existing_items:
                        items_to_delete.append(item)
                    else:
                        # Update quantity and price
                        quantity = self.request.POST.get(f'existing_quantity_{item.id}')
                        price = self.request.POST.get(f'existing_price_{item.id}')
                        if quantity and price:
                            item.quantity = int(quantity)
                            item.unit_price = Decimal(price)
                            item.subtotal = item.quantity * item.unit_price
                            item.save()
                
                # Delete removed items
                for item in items_to_delete:
                    item.delete()

                # Calculate new total
                po.calculate_total()
                po.save()

                messages.success(self.request, 'Purchase order updated successfully.')
                return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f'Error updating purchase order: {str(e)}')
            return self.form_invalid(form)

class AddItemsView(LoginRequiredMixin, UpdateView):
    model = PurchaseOrder
    template_name = 'purchasing/add_items.html'
    form_class = PurchaseOrderItemForm

    def dispatch(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponseRedirect:
        if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
            messages.error(request, "Only admin users can add items to purchase orders.")
            return redirect('purchasing:list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['po'] = self.object
        if self.object:
            for item in self.object.items.all():
                item.subtotal = item.quantity * item.unit_price
            context['items'] = self.object.items.all()
        context['available_items'] = InventoryItem.objects.all()
        return context

    def form_valid(self, form: PurchaseOrderItemForm) -> HttpResponseRedirect:
        form.instance.purchase_order = self.object
        form.save()
        messages.success(self.request, 'Item added successfully.')
        return redirect('purchasing:view_po', pk=self.object.pk)

class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'purchasing/supplier_form.html'
    success_url = reverse_lazy('purchasing:list')

    def dispatch(self, request, *args, **kwargs) -> Any:
        if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
            messages.error(request, "Only admin users can create suppliers.")
            return redirect('purchasing:list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form: SupplierForm) -> Any:
        response = super().form_valid(form)
        messages.success(self.request, 'Supplier created successfully.')
        return response

@login_required
def download_po_pdf(request, pk: int) -> Any:
    try:
        order = get_object_or_404(PurchaseOrder, pk=pk)
        pdf_filename = generate_purchase_order_pdf(order)
        file_path = os.path.join(settings.MEDIA_ROOT, 'purchase_orders', pdf_filename)
        
        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{pdf_filename}"'
                return response
        
        messages.error(request, "PDF file not found.")
        return redirect('purchasing:view_po', pk=pk)
        
    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect('purchasing:view_po', pk=pk)

def submit_purchase_order(request, pk: int) -> Any:
    if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
        messages.error(request, "Only admin users can submit purchase orders.")
        return redirect('purchasing:list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        if po.status == 'draft':
            po.status = 'pending_supplier'
            po.save()
            messages.success(request, 'Purchase order submitted for supplier approval.')
        else:
            messages.error(request, 'Purchase order can only be submitted from draft status.')
    return redirect('purchasing:list')

@login_required
def update_po_status(request, pk: int) -> Any:
    po = get_object_or_404(PurchaseOrder, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status and po.can_change_status(request.user, new_status):
            old_status = po.status
            po.status = new_status
            
            # Handle status-specific actions
            if new_status == 'supplier_accepted':
                po.status = 'in_transit'
                # Create a delivery record
                Delivery.objects.create(
                    purchase_order=po,
                    status='pending_delivery'
                )
            elif new_status == 'delivered':
                po.actual_delivery_date = timezone.now()
                
                # If verification file is uploaded
                if 'verification_file' in request.FILES:
                    po.delivery_verification_file = request.FILES['verification_file']
                    po.delivery_verified_by = request.user
                    po.delivery_verification_date = timezone.now()
            
            po.save()
            messages.success(request, f'Purchase order status updated from {old_status} to {new_status}.')
        else:
            messages.error(request, 'You do not have permission to change to this status.')
    
    return redirect('purchasing:view_po', pk=pk)

@login_required
def view_purchase_order(request, pk: int) -> Any:
    purchase_order = get_object_or_404(PurchaseOrder.objects.prefetch_related('items', 'items__item', 'deliveries'), pk=pk)
    
    # Debug: Print out the items associated with the purchase order
    print("\n====== DEBUG: Purchase Order Items ======")
    for item in purchase_order.items.all():
        print(f"Item: {item.item.item_name}, Quantity: {item.quantity}, Unit Price: {item.unit_price}")
    print("========================================\n")
    
    # Check user permissions
    if not hasattr(request.user, 'customuser'):
        messages.error(request, "User profile not found.")
        return redirect('purchasing:list')
    
    user_role = request.user.customuser.role
    can_view = False
    
    if user_role == 'admin':
        can_view = True
    elif user_role in ['manager', 'attendant']:
        can_view = purchase_order.warehouse in request.user.warehouses.all()
    
    if not can_view:
        messages.error(request, "You don't have permission to view this purchase order.")
        return redirect('purchasing:list')
    
    # Get available status changes for the user
    available_status_changes = []
    for status_choice in PurchaseOrder.STATUS_CHOICES:
        if purchase_order.can_change_status(request.user, status_choice[0]):
            available_status_changes.append(status_choice)
    
    context = {
        'purchase_order': purchase_order,
        'available_status_changes': available_status_changes,
        'user_role': user_role,
    }
    return render(request, 'purchasing/view_po.html', context)

@login_required
def receive_delivery(request, pk: int) -> Any:
    delivery = get_object_or_404(Delivery, pk=pk)
    po = delivery.purchase_order
    
    # Check user permissions
    if not hasattr(request.user, 'customuser'):
        messages.error(request, "You don't have permission to receive deliveries.")
        return redirect('purchasing:delivery_list')
    
    user_role = request.user.customuser.role
    if user_role != 'attendance' or po.warehouse not in request.user.warehouses.all():
        messages.error(request, "You don't have permission to receive this delivery.")
        return redirect('purchasing:delivery_list')
    
    if request.method == 'POST':
        form = DeliveryReceiptForm(request.POST, request.FILES)
        if form.is_valid():
            if delivery.status == 'in_delivery':  
                # Set delivery status and details
                delivery.status = 'pending_admin_confirmation'
                delivery.received_by = request.user
                delivery.delivery_date = timezone.now()
                
                # Handle receipt photo and confirmation file
                if 'receipt_photo' in request.FILES:
                    delivery.receipt_photo = request.FILES['receipt_photo']
                if 'delivery_confirmation_file' in request.FILES:
                    delivery.delivery_confirmation_file = request.FILES['delivery_confirmation_file']
                
                delivery.notes = form.cleaned_data.get('notes', '')
                delivery.save()
                
                # Update PO status
                po.status = 'delivered'
                po.actual_delivery_date = timezone.now()
                po.save()
                
                messages.success(request, 'Delivery receipt submitted. Waiting for admin confirmation.')
                return redirect('purchasing:delivery_list')
            else:
                messages.error(request, 'This delivery cannot be received in its current status.')
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = DeliveryReceiptForm()
    
    return render(request, 'purchasing/receive_delivery.html', {
        'delivery': delivery,
        'form': form,
        'po': po
    })

@login_required
def confirm_delivery(request, pk: int) -> Any:
    delivery = get_object_or_404(Delivery, pk=pk)
    po = delivery.purchase_order
    
    # Check user permissions
    if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
        messages.error(request, "Only admin users can confirm deliveries.")
        return redirect('purchasing:delivery_list')
    
    # Check if delivery is pending admin confirmation
    if delivery.status != 'pending_admin_confirmation':
        messages.error(request, "This delivery is not pending admin confirmation.")
        return redirect('purchasing:delivery_list')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            try:
                with transaction.atomic():
                    # Update inventory quantities
                    for delivery_item in delivery.items.all():
                        po_item = delivery_item.purchase_order_item
                        
                        # Try to find existing item in manager's warehouse first
                        inventory_item = InventoryItem.objects.filter(
                            warehouse=delivery.purchase_order.warehouse,
                            brand=po_item.item.brand,
                            model=po_item.item.model,
                            item_name=po_item.item.item_name,
                            location='manager_warehouse'
                        ).first()
                        
                        if inventory_item:
                            # Update existing item quantity
                            inventory_item.stock += delivery_item.quantity_delivered
                            inventory_item.save()
                        else:
                            # Create new inventory item in manager's warehouse
                            inventory_item = InventoryItem.objects.create(
                                warehouse=delivery.purchase_order.warehouse,
                                brand=po_item.item.brand,
                                category=po_item.item.category,
                                model=po_item.item.model,
                                item_name=po_item.item.item_name,
                                stock=delivery_item.quantity_delivered,
                                price=po_item.unit_price,
                                availability=True,
                                location='manager_warehouse'
                            )
                    
                    # Update delivery status
                    delivery.status = 'verified'
                    delivery.confirmed_by = request.user
                    delivery.confirmed_date = timezone.now()
                    delivery.save()
                    
                    # Update PO status to completed
                    po.status = 'completed'
                    po.save()
                    
                    messages.success(request, 'Delivery confirmed successfully. Inventory quantities have been updated in the manager warehouse.')
            except Exception as e:
                messages.error(request, f'Error confirming delivery: {str(e)}')
                return redirect('purchasing:delivery_list')
                
            return redirect('purchasing:delivery_list')
        elif action == 'reject':
            delivery.status = 'in_delivery'  # Reset to in_delivery for resubmission
            delivery.save()
            messages.warning(request, 'Delivery receipt rejected. Attendant needs to resubmit.')
            return redirect('purchasing:delivery_list')
    
    return render(request, 'purchasing/confirm_delivery.html', {
        'delivery': delivery,
        'po': po
    })

@login_required
def delivery_list(request) -> Any:
    # Get all deliveries first
    all_deliveries = Delivery.objects.select_related(
        'purchase_order',
        'purchase_order__supplier',
        'purchase_order__warehouse',
        'received_by',
        'confirmed_by'
    ).prefetch_related(
        'purchase_order__items',
        'purchase_order__items__item',
        'purchase_order__requisitions'
    )
    
    # Filter deliveries based on user role
    if hasattr(request.user, 'customuser'):
        user_role = request.user.customuser.role
        if user_role == 'admin':
            # Admin sees all deliveries
            deliveries = all_deliveries
        elif user_role == 'manager':
            # Get the warehouses this manager has access to
            manager_warehouses = request.user.warehouses.all()
            # Also get warehouses where they are assigned as manager via CustomUser
            manager_warehouses_via_role = Warehouse.objects.filter(custom_users__user=request.user, custom_users__role='manager')
            # Combine both sets of warehouses
            all_manager_warehouses = manager_warehouses | manager_warehouses_via_role
            # Managers see deliveries for their assigned warehouses
            deliveries = all_deliveries.filter(
                purchase_order__warehouse__in=all_manager_warehouses
            ).distinct()
        elif user_role == 'attendant':
            # Get the warehouses this attendant has access to
            attendant_warehouses = request.user.warehouses.all()
            # Also get warehouses where they are assigned as attendant via CustomUser
            attendant_warehouses_via_role = Warehouse.objects.filter(custom_users__user=request.user, custom_users__role='attendant')
            # Combine both sets of warehouses
            all_attendant_warehouses = attendant_warehouses | attendant_warehouses_via_role
            # Attendants see deliveries for their assigned warehouses
            deliveries = all_deliveries.filter(
                purchase_order__warehouse__in=all_attendant_warehouses
            ).distinct()
        else:
            deliveries = Delivery.objects.none()
    else:
        deliveries = Delivery.objects.none()
    
    # Order deliveries
    deliveries = deliveries.order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter and status_filter != 'all':
        deliveries = deliveries.filter(status=status_filter)
    
    # Get all status choices for the filter
    status_choices = [
        ('pending_delivery', 'Pending Delivery'),
        ('pending_confirmation', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled')
    ]
    
    context = {
        'deliveries': deliveries,
        'current_time': timezone.now(),
        'current_status': status_filter or 'all',
        'status_choices': status_choices,
        'title': 'Deliveries'
    }
    return render(request, 'purchasing/delivery_list.html', context)

@login_required
def view_delivery(request, pk: int) -> Any:
    delivery = get_object_or_404(Delivery.objects.select_related(
        'purchase_order',
        'purchase_order__supplier',
        'received_by'
    ).prefetch_related(
        'items',
        'items__purchase_order_item',
        'items__purchase_order_item__item'
    ), pk=pk)

    # Check if user has permission to view this delivery
    if hasattr(request.user, 'customuser'):
        user_role = request.user.customuser.role
        user_warehouses = request.user.customuser.warehouses.all()
        
        if user_role == 'admin':
            # Admin can view all deliveries
            pass
        elif user_role in ['manager', 'attendant']:
            # Check if delivery is to user's warehouse
            if not (delivery.purchase_order and delivery.purchase_order.warehouse in user_warehouses):
                messages.error(request, "You don't have permission to view this delivery.")
                return redirect('purchasing:delivery_list')
        else:
            messages.error(request, "You don't have permission to view deliveries.")
            return redirect('purchasing:delivery_list')
    else:
        messages.error(request, "You don't have permission to view deliveries.")
        return redirect('purchasing:delivery_list')
    
    # Handle receipt upload by manager
    if request.method == 'POST' and delivery.status == 'in_delivery':
        if request.user.customuser.role != 'manager':
            messages.error(request, "Only managers can upload delivery receipts.")
            return redirect('purchasing:delivery_list')
            
        form = DeliveryReceiptForm(request.POST, request.FILES, instance=delivery)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.delivery_date = timezone.now()  # Set the delivery date
            delivery.status = 'pending_admin_confirmation'
            delivery.save()
            messages.success(request, "Delivery receipt uploaded successfully. Awaiting admin confirmation.")
            return redirect('purchasing:view_delivery', pk=pk)
    else:
        form = DeliveryReceiptForm(instance=delivery)
    
    context = {
        'delivery': delivery,
        'form': form,
        'po': delivery.purchase_order
    }
    return render(request, 'purchasing/view_delivery.html', context)

@login_required
def start_delivery(request, pk: int) -> Any:
    delivery = get_object_or_404(Delivery, pk=pk)
    if delivery.status != 'pending_delivery':
        messages.error(request, "This delivery cannot be started.")
        return redirect('purchasing:delivery_list')

    delivery.status = 'in_delivery'
    delivery.save()
    messages.success(request, "Delivery started successfully.")
    return redirect('purchasing:delivery_list')

@login_required
def clear_delivery_history(request) -> Any:
    if not request.user.customuser.role == 'manager':
        messages.error(request, "Only managers can clear delivery history.")
        return redirect('purchasing:delivery_list')

    if request.method == 'POST':
        # Delete all received deliveries
        Delivery.objects.filter(status='received').delete()
        messages.success(request, "Delivery history has been cleared successfully.")
    
    return redirect('purchasing:delivery_list')

@login_required
def generate_po_pdf(request, pk: int) -> HttpResponse:
    try:
        order = get_object_or_404(PurchaseOrder, pk=pk)
        # Get the template
        template = get_template('purchasing/po_pdf.html')
        
        # Prepare context
        context = {
            'order': order,
            'items': order.items.all(),
            'company_name': 'Your Company Name',  # Customize this
            'company_address': 'Your Company Address',  # Customize this
            'company_phone': 'Your Company Phone',  # Customize this
            'company_email': 'your@email.com',  # Customize this
        }
        
        # Render the template
        html = template.render(context)
        
        # Create PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
        
        # Return the PDF as response
        if not pdf.err:
            response = HttpResponse(result.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="PO_{order.po_number}.pdf"'
            return response
        
        return HttpResponse(b'Error generating PDF', status=500)
    except Exception as e:
        return HttpResponse(b'Error generating PDF', status=500)

@login_required
def delete_item(request, po_pk: int, item_pk: int) -> Any:
    item = get_object_or_404(PurchaseOrderItem, pk=item_pk)
    item.delete()
    return redirect('purchasing:view_po', pk=po_pk)

@login_required
def confirm_purchase_order(request, pk: int) -> Any:
    print("\n=== Debug Confirm Purchase Order ===")
    po = get_object_or_404(PurchaseOrder, pk=pk)
    print(f"Purchase Order: {po.po_number}")
    print(f"PO Warehouse: {po.warehouse.name if po.warehouse else 'None'}")
    
    if request.user.customuser.role != 'admin':
        messages.error(request, "You don't have permission to confirm this purchase order.")
        return redirect('purchasing:list')
    
    try:
        if not po.warehouse:
            raise ValueError("Purchase order must have a warehouse assigned")
            
        # Create a delivery record
        delivery = Delivery.objects.create(
            purchase_order=po,
            status='pending_delivery'  # Changed to pending_delivery as initial status
        )
        print(f"Created delivery {delivery.pk}")
        
        # Create delivery items for each PO item
        for po_item in po.items.all():
            DeliveryItem.objects.create(
                delivery=delivery,
                purchase_order_item=po_item,
                quantity_delivered=po_item.quantity
            )
            print(f"Created delivery item for: {po_item.item.item_name} - {po_item.quantity} units")
        
        # Update PO status
        po.status = 'confirmed'
        po.save()
        print("Updated PO status to 'confirmed'")
        
        messages.success(request, 'Purchase order confirmed successfully and delivery record created.')
    except Exception as e:
        print(f"Error in confirm_purchase_order: {str(e)}")
        messages.error(request, f'Error confirming purchase order: {str(e)}')
    
    print("=== End Debug ===\n")
    return redirect('purchasing:list')

@login_required
def upcoming_deliveries(request) -> Any:
    user_warehouses = request.user.warehouses.all()
    
    # Get deliveries that are pending or in transit
    upcoming_deliveries = Delivery.objects.filter(
        Q(purchase_order__warehouse__in=user_warehouses) |
        Q(purchase_order__warehouse__isnull=True, warehouse__in=user_warehouses),
        status__in=['pending_delivery', 'in_transit']
    ).select_related(
        'purchase_order',
        'purchase_order__supplier',
        'requisition'
    ).order_by('created_at')
    
    # Get POs that are confirmed but don't have deliveries yet
    confirmed_pos = PurchaseOrder.objects.filter(
        warehouse__in=user_warehouses,
        status='confirmed'
    ).order_by('expected_delivery_date')
    
    context = {
        'upcoming_deliveries': upcoming_deliveries,
        'confirmed_pos': confirmed_pos,
    }
    return render(request, 'purchasing/upcoming_deliveries.html', context)

@login_required
def create_purchase_order(request, requisition_id=None):
    requisition = None
    if requisition_id:
        requisition = get_object_or_404(Requisition, id=requisition_id)

    suppliers = Supplier.objects.all()
    warehouses = Warehouse.objects.filter(
        name__in=['Attendant Warehouse', 'Manager Warehouse']
    )
    available_items = InventoryItem.objects.all()

    if request.method == 'POST':
        print("\n====== DEBUG: POST DATA ======")
        print("Raw POST data:")
        for key, value in request.POST.items():
            print(f"{key}: {value}")
        
        # Deserialize items_data
        items_data = json.loads(request.POST.get('items_data', '[]'))
        print("Deserialized items data:", items_data)
        
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    print("\n====== Creating Purchase Order ======")
                    # Create the purchase order
                    po = form.save(commit=False)
                    po.created_by = request.user
                    po.status = 'pending_supplier'
                    po.save()
                    print(f"Created PO: {po.po_number}")

                    if requisition:
                        # Add requisition to purchase order
                        po.requisitions.add(requisition)
                        # Add requisition items to purchase order
                        for req_item in requisition.items.all():
                            PurchaseOrderItem.objects.create(
                                purchase_order=po,
                                item=req_item.item,
                                quantity=req_item.quantity,
                                unit_price=req_item.item.price,
                                brand=req_item.item.brand.name,
                                model_name=req_item.item.model
                            )
                    else:
                        # Process deserialized items
                        print("\n====== Processing Deserialized Items ======")
                        for item_data in items_data:
                            try:
                                print(f"\nCreating new item:")
                                print(f"Data: {item_data}")
                                
                                # Create or get brand
                                brand, _ = Brand.objects.get_or_create(name=item_data['brand'])
                                print(f"Using brand: {brand}")
                                
                                # Create new inventory item
                                item = InventoryItem.objects.create(
                                    item_name=item_data['itemName'],
                                    brand=brand,
                                    model=item_data['model'],
                                    warehouse=po.warehouse,
                                    category=Category.objects.get_or_create(name='General')[0],
                                    stock=0,
                                    price=Decimal(item_data['unitPrice']),
                                    availability=True,
                                    location='manager_warehouse'
                                )
                                print(f"Created inventory item: {item}")
                                
                                # Create purchase order item
                                po_item = PurchaseOrderItem.objects.create(
                                    purchase_order=po,
                                    item=item,
                                    quantity=int(item_data['quantity']),
                                    unit_price=Decimal(item_data['unitPrice']),
                                    brand=item_data['brand'],
                                    model_name=item_data['model']
                                )
                                print(f"Created PO item: {po_item}")
                                
                                # Verify the item was created
                                print(f"Verifying PO item exists: {PurchaseOrderItem.objects.filter(id=po_item.id).exists()}")
                                print(f"PO item details: {vars(po_item)}")
                            except Exception as e:
                                print(f"Error creating item: {str(e)}")
                                raise
                        
                    # Update total amount
                    print("\n====== Updating Total Amount ======")
                    po.total_amount = sum(item.unit_price * item.quantity for item in po.items.all())
                    po.save()
                    print(f"Updated total amount: {po.total_amount}")

                    messages.success(request, 'Purchase order created successfully.')
                    return redirect('purchasing:view', pk=po.id)
            except Exception as e:
                print(f"Error creating purchase order: {str(e)}")
                messages.error(request, 'An error occurred while creating the purchase order.')

    context = {
        'form': form,
        'suppliers': suppliers,
        'warehouses': warehouses,
        'available_items': available_items,
        'requisition': requisition
    }
    return render(request, 'purchasing/purchase_order_form.html', context)

@login_required
def upload_delivery_image(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    
    # Check if user is attendant or manager
    if request.user.customuser.role not in ['attendant', 'manager']:
        messages.error(request, 'You do not have permission to upload delivery images.')
        return redirect('purchasing:view_delivery', pk=pk)
    
    # Check if delivery is in pending_delivery status
    if delivery.status != 'pending_delivery':
        messages.error(request, 'Delivery image can only be uploaded for pending deliveries.')
        return redirect('purchasing:view_delivery', pk=pk)
    
    if request.method == 'POST':
        try:
            # Handle image upload
            delivery_image = request.FILES.get('delivery_image')
            delivery_note = request.POST.get('delivery_note', '')
            
            if not delivery_image:
                messages.error(request, 'Please select an image to upload.')
                return redirect('purchasing:view_delivery', pk=pk)
            
            # Update delivery with image and note
            delivery.delivery_image = delivery_image
            delivery.delivery_note = delivery_note
            delivery.received_by = request.user
            delivery.received_date = timezone.now()
            delivery.delivery_date = timezone.now()  # Set the delivery date
            delivery.status = 'pending_confirmation'
            delivery.save()
            
            messages.success(request, 'Delivery image uploaded successfully.')
            return redirect('purchasing:view_delivery', pk=pk)
            
        except Exception as e:
            messages.error(request, f'Error uploading delivery image: {str(e)}')
            return redirect('purchasing:view_delivery', pk=pk)
    
    return redirect('purchasing:view_delivery', pk=pk)

@login_required
def confirm_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    
    # Check if user is admin
    if request.user.customuser.role != 'admin':
        messages.error(request, 'Only admin can confirm deliveries.')
        return redirect('purchasing:view_delivery', pk=pk)
    
    # Check if delivery is pending confirmation
    if delivery.status != 'pending_confirmation':
        messages.error(request, 'Only pending confirmation deliveries can be confirmed.')
        return redirect('purchasing:view_delivery', pk=pk)
    
    try:
        delivery.status = 'confirmed'
        delivery.confirmed_by = request.user
        delivery.confirmed_date = timezone.now()
        delivery.save()
        
        messages.success(request, 'Delivery confirmed successfully.')
    except Exception as e:
        messages.error(request, f'Error confirming delivery: {str(e)}')
    
    return redirect('purchasing:view_delivery', pk=pk)