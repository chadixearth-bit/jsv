from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db import transaction
from django.utils import timezone
from django.db.models import F, Sum, Manager, QuerySet
from django.template.loader import get_template
from typing import Any, Dict, Optional, Type, Union
import json
from decimal import Decimal
from io import BytesIO
from xhtml2pdf import pisa
import os
import traceback

# Local models
from .models import (
    PurchaseOrder, PurchaseOrderItem, Supplier, Warehouse,
    PendingPOItem, Delivery, DeliveryItem
)
from .forms import PurchaseOrderForm, PurchaseOrderItemForm, SupplierForm, DeliveryReceiptForm

# External models
from inventory.models import Brand, InventoryItem, Warehouse, Category
from requisition.models import Requisition, RequisitionItem

# Type hints for Django models
PurchaseOrder.objects: Manager[PurchaseOrder]
PurchaseOrderItem.objects: Manager[PurchaseOrderItem]
PendingPOItem.objects: Manager[PendingPOItem]
Supplier.objects: Manager[Supplier]
Brand.objects: Manager[Brand]
InventoryItem.objects: Manager[InventoryItem]
Requisition.objects: Manager[Requisition]
RequisitionItem.objects: Manager[RequisitionItem]
Delivery.objects: Manager[Delivery]
DeliveryItem.objects: Manager[DeliveryItem]
Warehouse.objects: Manager[Warehouse]
Category.objects: Manager[Category]

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchasing/purchase_order_list.html'
    context_object_name = 'purchase_orders'

    def get_queryset(self) -> QuerySet[Any]:
        return PurchaseOrder.objects.select_related('supplier').order_by('-order_date', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get pending items grouped by brand
        pending_items = PendingPOItem.objects.filter(
            is_processed=False
        ).select_related(
            'brand',
            'item__item',
            'item__requisition',
            'item__requisition__requester'
        ).order_by('brand__name', 'created_at')
        
        # Group items by brand
        pending_by_brand = {}
        for item in pending_items:
            brand_name = item.brand.name
            if brand_name not in pending_by_brand:
                pending_by_brand[brand_name] = []
            pending_by_brand[brand_name].append(item)
        
        context['pending_requisitions_by_brand'] = pending_by_brand
        context['suppliers'] = Supplier.objects.all()
        context['warehouses'] = Warehouse.objects.filter(
            name__in=['Attendant Warehouse', 'Manager Warehouse']
        )
        return context

class PurchaseOrderCreateView(LoginRequiredMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchasing/purchase_order_form.html'

    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
            messages.error(request, "Only admin users can create purchase orders.")
            return redirect('purchasing:list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Always add suppliers and warehouses to context
        context['suppliers'] = Supplier.objects.all()
        warehouses = Warehouse.objects.filter(
            name__in=['Attendant Warehouse', 'Manager Warehouse']
        )
        context['warehouses'] = warehouses
        context['inventory_items'] = InventoryItem.objects.select_related('brand', 'warehouse').filter(
            warehouse__in=warehouses
        )
        
        if 'po_draft_data' in self.request.session:
            draft_data = self.request.session['po_draft_data']
            print("\nFound PO draft data:", draft_data)  # Debug print
            
            # Get the actual objects for supplier and warehouse
            try:
                supplier = Supplier.objects.get(id=draft_data['supplier'])
                warehouse = Warehouse.objects.get(id=draft_data['warehouse'])
                
                initial_data = {
                    'supplier': draft_data['supplier'],  # Use ID instead of object
                    'warehouse': draft_data['warehouse'],  # Use ID instead of object
                    'order_date': timezone.now().date(),
                    'expected_delivery_date': draft_data['expected_delivery_date'],
                    'notes': draft_data['notes']
                }
                print("\nInitial data:", initial_data)  # Debug print
                
                # Get the pending items
                pending_items = draft_data.get('pending_items', [])
                print("\nPending items:", pending_items)  # Debug print
                
                # Store data in context
                context.update({
                    'initial': initial_data,
                    'pending_items': pending_items,
                    'brand': draft_data.get('brand'),
                    'draft_data': draft_data
                })
                
            except (Supplier.DoesNotExist, Warehouse.DoesNotExist) as e:
                messages.error(self.request, f"Error loading draft data: {str(e)}")
        
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Set basic PO data
                po = form.save(commit=False)
                po.created_by = self.request.user
                po.order_date = timezone.now().date()
                po.status = 'draft'
                
                # Get items data from form
                items_data = json.loads(self.request.POST.get('items', '[]'))
                form.cleaned_data['items'] = items_data
                
                # Save the PO and items
                po = form.save()

                # Mark pending items as processed if they exist
                if 'po_draft_data' in self.request.session:
                    pending_item_ids = [item.get('pending_item_id') for item in self.request.session['po_draft_data'].get('pending_items', [])]
                    if pending_item_ids:
                        PendingPOItem.objects.filter(id__in=pending_item_ids).update(is_processed=True)
                    del self.request.session['po_draft_data']
                    self.request.session.modified = True

                # Calculate total
                po.calculate_total()
                po.save()
                
                messages.success(self.request, "Purchase order created successfully")
                return redirect('purchasing:list')
                
        except Exception as e:
            messages.error(self.request, f"Error creating purchase order: {str(e)}")
            return self.form_invalid(form)

    def get_initial(self):
        initial = super().get_initial()
        if 'po_draft_data' in self.request.session:
            draft_data = self.request.session['po_draft_data']
            initial.update({
                'supplier': draft_data.get('supplier'),
                'warehouse': draft_data.get('warehouse'),
                'expected_delivery_date': draft_data.get('expected_delivery_date'),
                'notes': draft_data.get('notes')
            })
        return initial

    def get_success_url(self):
        return reverse('purchasing:list')

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

@login_required
def submit_purchase_order(request, pk: int) -> Any:
    if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
        messages.error(request, "Only admin users can submit purchase orders.")
        return redirect('purchasing:list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        if po.status == 'draft':
            try:
                with transaction.atomic():
                    # Update PO status
                    po.status = 'pending_supplier'
                    po.save()

                    # Get all items in this PO
                    po_items = po.purchaseorderitem_set.all()
                    
                    # Find and mark corresponding pending items as processed
                    for po_item in po_items:
                        pending_items = PendingPOItem.objects.filter(
                            item__item=po_item.item,
                            is_processed=False
                        )
                        if pending_items.exists():
                            pending_items.update(is_processed=True)

                    messages.success(request, 'Purchase order submitted for supplier approval.')
            except Exception as e:
                print(f"Error submitting PO: {str(e)}")
                import traceback
                traceback.print_exc()
                messages.error(request, f'Error submitting purchase order: {str(e)}')
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
    print("\n====== DEBUG: Purchase Order Items in View ======")
    print(f"PO ID: {purchase_order.id}")
    print(f"PO Number: {purchase_order.po_number}")
    print(f"Total Amount: {purchase_order.total_amount}")
    print(f"Number of items: {purchase_order.items.count()}")
    print("Items:")
    for item in purchase_order.items.all():
        item_name = item.item.item_name if item.item else item.item_name
        print(f"- Item: {item_name}, Qty: {item.quantity}, Price: {item.unit_price}, Brand: {item.brand}, Model: {item.model_name}")
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
def confirm_delivery(request, pk):
    delivery = get_object_or_404(Delivery.objects.select_related(
        'purchase_order',
        'purchase_order__supplier',
        'purchase_order__warehouse',
        'received_by',
        'confirmed_by'
    ).prefetch_related(
        'items',
        'items__purchase_order_item',
        'items__purchase_order_item__item'
    ), pk=pk)
    
    # Check if user is admin
    if request.user.customuser.role != 'admin':
        messages.error(request, 'Only admin can confirm deliveries.')
        return redirect('purchasing:view_delivery', pk=pk)
    
    # Check if delivery is pending confirmation
    if delivery.status != 'pending_confirmation':
        messages.error(request, f'Only pending confirmation deliveries can be confirmed. Current status: {delivery.status}')
        return redirect('purchasing:view_delivery', pk=pk)
    
    try:
        with transaction.atomic():
            # Update delivery status
            delivery.status = 'confirmed'
            delivery.confirmed_by = request.user
            delivery.confirmed_date = timezone.now()
            delivery.save()
            
            # Update inventory quantities
            warehouse = delivery.purchase_order.warehouse
            
            for delivery_item in delivery.items.all():
                po_item = delivery_item.purchase_order_item
                
                # Find the exact matching item in the warehouse
                matching_item = InventoryItem.objects.filter(
                    warehouse=warehouse,
                    item_name=po_item.item.item_name if po_item.item else po_item.item_name,
                    brand__name=po_item.brand,
                    model=po_item.model_name
                ).first()
                
                if matching_item:
                    # Update existing item
                    original_stock = matching_item.stock
                    matching_item.stock += delivery_item.quantity_delivered
                    matching_item.save()
                    print(f"Updated {matching_item.item_name} (Brand: {matching_item.brand.name}, Model: {matching_item.model}) stock from {original_stock} to {matching_item.stock}")
                    messages.info(request, f"Updated {matching_item.item_name} (Brand: {matching_item.brand.name}, Model: {matching_item.model}) stock from {original_stock} to {matching_item.stock}")
                else:
                    # Create new item in warehouse if it doesn't exist
                    new_item = InventoryItem.objects.create(
                        warehouse=warehouse,
                        item_name=po_item.item.item_name if po_item.item else po_item.item_name,
                        brand=po_item.brand,
                        model=po_item.model_name,
                        category=po_item.item.category if po_item.item else None,
                        stock=delivery_item.quantity_delivered,
                        price=po_item.unit_price,
                        availability=True
                    )
                    print(f"Created new item {new_item.item_name} (Brand: {new_item.brand.name}, Model: {new_item.model}) with initial stock {new_item.stock}")
                    messages.info(request, f"Created new item {new_item.item_name} (Brand: {new_item.brand.name}, Model: {new_item.model}) with initial stock {new_item.stock}")
            
            # Update PO status
            po = delivery.purchase_order
            po.status = 'completed'
            po.save()
        
        messages.success(request, 'Delivery confirmed successfully and inventory updated.')
    except Exception as e:
        print(f"Error in confirm_delivery: {str(e)}")
        messages.error(request, f'Error confirming delivery: {str(e)}')
    
    return redirect('purchasing:view_delivery', pk=pk)

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
            # Managers see deliveries for Manager Warehouse
            deliveries = all_deliveries.filter(
                purchase_order__warehouse__name='Manager Warehouse'
            )
        elif user_role == 'attendant':
            # Attendants see deliveries for Attendant Warehouse
            deliveries = all_deliveries.filter(
                purchase_order__warehouse__name='Attendant Warehouse'
            )
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
        'purchase_order__warehouse',
        'received_by'
    ).prefetch_related(
        'items',
        'items__purchase_order_item',
        'items__purchase_order_item__item'
    ), pk=pk)

    # Check if user has permission to view this delivery
    if hasattr(request.user, 'customuser'):
        user_role = request.user.customuser.role
        
        if user_role == 'admin':
            # Admin can view all deliveries
            pass
        elif user_role == 'manager':
            # Manager can only view Manager Warehouse deliveries
            if not delivery.purchase_order or delivery.purchase_order.warehouse.name != 'Manager Warehouse':
                messages.error(request, "You don't have permission to view this delivery.")
                return redirect('purchasing:delivery_list')
        elif user_role == 'attendant':
            # Attendant can only view Attendant Warehouse deliveries
            if not delivery.purchase_order or delivery.purchase_order.warehouse.name != 'Attendant Warehouse':
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
            item_name = po_item.item.item_name if po_item.item else po_item.item_name
            print(f"Created delivery item for: {item_name} - {po_item.quantity} units")
        
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
    initial_items = []
    initial_data = {}
    
    # Check for session data from pending items
    po_draft_data = request.session.get('po_draft_data')
    if po_draft_data:
        print("Found PO draft data:", po_draft_data)  # Debug print
        
        try:
            print("Processing initial data...")  # Debug print
            
            # Get supplier and warehouse objects
            supplier = get_object_or_404(Supplier, id=po_draft_data['supplier'])
            warehouse = get_object_or_404(Warehouse, id=po_draft_data['warehouse'])
            
            # Set initial data for the form
            initial_data = {
                'supplier': po_draft_data['supplier'],  # Use ID instead of object
                'warehouse': po_draft_data['warehouse'],  # Use ID instead of object
                'order_date': timezone.now().date(),
                'expected_delivery_date': po_draft_data.get('expected_delivery_date'),
                'notes': po_draft_data.get('notes', '')
            }
            print("Initial data prepared:", initial_data)  # Debug print
            
            # Convert pending items to initial items format
            pending_items = po_draft_data.get('pending_items', [])
            print("Pending items:", pending_items)  # Debug print
            
            for item_data in pending_items:
                try:
                    item_dict = {
                        'brand': item_data['brand'],
                        'item_name': item_data['itemName'],
                        'model': item_data['model'],
                        'quantity': item_data['quantity'],
                        'unit_price': float(item_data['unit_price'])
                    }
                    print("Adding item:", item_dict)  # Debug print
                    initial_items.append(item_dict)
                except KeyError as e:
                    print(f"Missing key in item_data: {e}")
                    continue
            
            print("Final initial items:", initial_items)  # Debug print
        
        except Exception as e:
            print(f"Error processing session data: {str(e)}")
            print("Full traceback:")  # Debug print
            import traceback
            traceback.print_exc()  # Debug print
            messages.error(request, f"Error processing session data: {str(e)}")
            # Clear invalid session data
            if 'po_draft_data' in request.session:
                del request.session['po_draft_data']

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            po = form.save(commit=False)
            po.created_by = request.user
            po.order_date = timezone.now().date()
            po.status = 'draft'
            
            # Get items data from form
            items_data = json.loads(request.POST.get('items', '[]'))
            form.cleaned_data['items'] = items_data
            
            # Save the PO and items
            po = form.save()

            # Mark pending items as processed if they exist
            if 'po_draft_data' in request.session:
                pending_item_ids = [item.get('pending_item_id') for item in request.session['po_draft_data'].get('pending_items', [])]
                if pending_item_ids:
                    PendingPOItem.objects.filter(id__in=pending_item_ids).update(is_processed=True)
                del request.session['po_draft_data']
                request.session.modified = True

            # Calculate total amount
            po.calculate_total()

            messages.success(request, 'Purchase order created successfully.')
            return redirect('purchasing:list')
        else:
            print("Form errors:", form.errors)  # Debug print
    else:
        # For GET requests, create a new form with initial data
        print("Creating form with initial data:", initial_data)  # Debug print
        form = PurchaseOrderForm(user=request.user, initial=initial_data)
        print("Form created. Initial data in form:", form.initial)  # Debug print

    context = {
        'form': form,
        'initial_items': json.dumps(initial_items) if initial_items else '[]',
        'suppliers': Supplier.objects.all(),
        'warehouses': Warehouse.objects.filter(
            name__in=['Attendant Warehouse', 'Manager Warehouse']
        ),
        'inventory_items': InventoryItem.objects.select_related('brand', 'warehouse').filter(
            warehouse__in=Warehouse.objects.filter(
                name__in=['Attendant Warehouse', 'Manager Warehouse']
            )
        ),
        'is_edit': False
    }
    print("Context prepared. Initial items:", context['initial_items'])  # Debug print
    return render(request, 'purchasing/purchase_order_form.html', context)

@login_required
def create_po_from_requisition(request, requisition_id):
    """Add requisition items to existing draft PO or create new one"""
    requisition = get_object_or_404(Requisition, pk=requisition_id)
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None

    if user_role != 'admin':
        messages.error(request, "Only admin can manage purchase orders.")
        return redirect('requisition:requisition_list')

    if requisition.status != 'pending_admin_approval':
        messages.error(request, "This requisition is not pending admin review.")
        return redirect('requisition:requisition_list')

    try:
        with transaction.atomic():
            # Find existing draft PO
            draft_po = PurchaseOrder.objects.filter(status='draft').order_by('-created_at').first()

            if not draft_po:
                # If no draft PO exists, create one
                supplier = Supplier.objects.first()
                if not supplier:
                    messages.error(request, "No suppliers found. Please create a supplier first.")
                    return redirect('purchasing:add_supplier')

                draft_po = PurchaseOrder.objects.create(
                    created_by=request.user,
                    status='draft',
                    supplier=supplier,
                    warehouse=requisition.destination_warehouse or requisition.requester.customuser.warehouses.first(),
                    order_date=timezone.now().date(),
                    expected_delivery_date=timezone.now().date() + timezone.timedelta(days=7),
                    notes="Draft PO for pending requisitions"
                )

            # Add items from requisition to PO
            for req_item in requisition.items.all():
                # Check if item already exists in PO
                existing_item = PurchaseOrderItem.objects.filter(
                    purchase_order=draft_po,
                    item=req_item.item
                ).first()

                if existing_item:
                    # Update quantity if item exists
                    existing_item.quantity += req_item.quantity
                    existing_item.save()
                else:
                    # Create new item if it doesn't exist
                    PurchaseOrderItem.objects.create(
                        purchase_order=draft_po,
                        item=req_item.item,
                        brand=req_item.item.brand.name if req_item.item.brand else '',
                        model_name=req_item.item.model or '',
                        quantity=req_item.quantity,
                        unit_price=Decimal('0.00')  # You may want to set a default price
                    )

                # Link requisition to PO and update its status
                draft_po.requisitions.add(requisition)
                requisition.status = 'pending_po'
                requisition.save()

            messages.success(request, f'Items from requisition #{requisition.id} added to Purchase Order #{draft_po.id}')
            return redirect('purchasing:view_purchase_order', pk=draft_po.id)

    except Exception as e:
        messages.error(request, f"Error adding items to purchase order: {str(e)}")
        return redirect('requisition:requisition_list')

@login_required
@transaction.atomic
def create_bulk_po(request):
    if request.method != 'POST':
        return redirect('purchasing:pending_po_items')

    # Get all brands with pending items
    brands = Brand.objects.filter(pendingpoitem__is_processed=False).distinct()
    
    success_count = 0
    error_count = 0
    
    for brand in brands:
        try:
            pending_items = PendingPOItem.objects.filter(
                brand=brand,
                is_processed=False
            )
            
            if pending_items.exists():
                # Create new PO for this brand
                po = PurchaseOrder.objects.create(
                    status='pending_supplier',
                    created_by=request.user
                )
                
                # Generate PO number
                po.po_number = f'PO{str(po.id).zfill(6)}'
                po.save()
                
                # Add items to PO
                for pending_item in pending_items:
                    PurchaseOrderItem.objects.create(
                        purchase_order=po,
                        item=pending_item.item.item,
                        quantity=pending_item.quantity,
                        brand=brand
                    )
                    
                    # Mark pending item as processed
                    pending_item.is_processed = True
                    pending_item.save()
                
                success_count += 1
                
        except Exception as e:
            error_count += 1
            messages.error(request, f'Error creating PO for {brand.name}: {str(e)}')
            continue
    
    if success_count > 0:
        messages.success(request, f'Successfully created {success_count} purchase orders.')
    if error_count > 0:
        messages.warning(request, f'Failed to create {error_count} purchase orders. Check the error messages above.')
    
    return redirect('purchasing:pending_po_items')

@login_required
@transaction.atomic
def create_po_from_pending_form(request):
    if request.method != 'POST':
        return redirect('purchasing:pending_po_items')
        
    brand_id = request.POST.get('brand_id')
    if not brand_id:
        messages.error(request, 'No brand ID provided')
        return redirect('purchasing:pending_po_items')
        
    brand = get_object_or_404(Brand, id=brand_id)
    pending_items = PendingPOItem.objects.filter(
        brand=brand,  # Use brand object directly since it's a ForeignKey
        is_processed=False
    ).select_related('item__item')
    
    if not pending_items.exists():
        messages.error(request, f'No pending items found for {brand.name}')
        return redirect('purchasing:pending_po_items')
    
    try:
        # Create new PO
        po = PurchaseOrder.objects.create(
            status='pending_supplier',
            created_by=request.user,
            supplier=Supplier.objects.get(brand=brand),  # Set the supplier
            order_date=timezone.now().date(),
            expected_delivery_date=timezone.now().date() + timezone.timedelta(days=7)  # Default to 7 days from now
        )
        
        # Generate PO number
        po.po_number = f'PO{str(po.id).zfill(6)}'
        po.save()
        
        # Add items to PO
        for pending_item in pending_items:
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                item=pending_item.item.item,
                brand=brand.name,  # Use brand.name for the string field in PO item
                model_name=pending_item.item.item.model,
                quantity=pending_item.quantity,
                unit_price=pending_item.item.item.price or Decimal('0.00')
            )
            
            # Mark pending item as processed
            pending_item.is_processed = True
            pending_item.save()
            
            # Link requisition to PO if it exists
            if pending_item.item.requisition:
                po.requisitions.add(pending_item.item.requisition)
        
        # Calculate total and save
        po.calculate_total()
        po.save()
            
        messages.success(request, f'Successfully created purchase order for {brand.name}')
        return redirect('purchasing:view_purchase_order', pk=po.id)
        
    except Brand.DoesNotExist:
        messages.error(request, f'Brand with ID {brand_id} not found')
        return redirect('purchasing:pending_po_items')
    except Exception as e:
        messages.error(request, f'Error creating purchase order: {str(e)}')
        return redirect('purchasing:pending_po_items')

@login_required
def clear_pending_items(request):
    """Clear all pending PO items for a specific brand"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data = json.loads(request.body)
        brand = data.get('brand')

        if not brand:
            return JsonResponse({'success': False, 'error': 'Brand is required'})

        # Get all pending requisitions with items of this brand
        requisitions = Requisition.objects.filter(
            status='pending_admin_approval',
            items__item__brand__name=brand
        ).distinct()
        
        # Update their status
        requisitions.update(status='rejected')

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def create_from_pending_items(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print("Received data:", data)  # Debug print
            
            # Get selected items with all related data
            selected_items = PendingPOItem.objects.filter(
                id__in=data.get('selected_items', []),
                is_processed=False
            ).select_related(
                'brand',
                'item__item',  # Get inventory item
                'item__requisition'  # Get requisition
            )
            
            print(f"Found {selected_items.count()} selected items")  # Debug print
            
            # Store data in session
            request.session['po_draft_data'] = {
                'supplier': data.get('supplier'),
                'warehouse': data.get('warehouse'),
                'expected_delivery_date': data.get('expected_delivery_date'),
                'notes': data.get('notes', ''),
                'pending_items': []
            }
            
            # Add items to session data
            for pending_item in selected_items:
                inventory_item = pending_item.item.item  # Get the inventory item
                request.session['po_draft_data']['pending_items'].append({
                    'brand': inventory_item.brand.name,
                    'item_name': inventory_item.item_name,
                    'model': inventory_item.model,
                    'quantity': pending_item.quantity,
                    'unit_price': str(inventory_item.price),  # Get price from inventory item
                    'pending_item_id': pending_item.id  # Store the ID to mark as processed later
                })
            
            print("Session data:", request.session['po_draft_data'])  # Debug print
            request.session.modified = True
            
            return JsonResponse({
                'status': 'success', 
                'redirect_url': reverse('purchasing:create_purchase_order')
            })
            
        except Exception as e:
            print(f"Error in create_from_pending_items: {str(e)}")  # Debug print
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)

@login_required
def create_po_from_pending(request, brand=None):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        data = json.loads(request.body)
        supplier_id = data.get('supplier')
        warehouse_id = data.get('warehouse')
        expected_delivery_date = data.get('expected_delivery_date')
        notes = data.get('notes', '')
        brand = brand or data.get('brand')  # Get brand from URL param or request data

        # Validate required fields
        if not all([supplier_id, warehouse_id, expected_delivery_date]):
            return JsonResponse({'success': False, 'error': 'Missing required fields'})

        try:
            # Get pending items for this brand
            pending_items_query = PendingPOItem.objects.filter(is_processed=False)
            if brand:
                pending_items_query = pending_items_query.filter(brand__name=brand)
            
            pending_items = pending_items_query.select_related('item__item')

            if not pending_items.exists():
                error_msg = f'No pending items found' + (f' for brand {brand}' if brand else '')
                return JsonResponse({'success': False, 'error': error_msg})

            # Store the data in session
            request.session['po_draft_data'] = {
                'supplier': supplier_id,
                'warehouse': warehouse_id,
                'expected_delivery_date': expected_delivery_date,
                'notes': notes,
                'brand': brand,
                'pending_items': [
                    {
                        'item_id': item.item.item.id,
                        'quantity': item.quantity,
                        'unit_price': str(item.item.item.price or Decimal('0.00')),
                        'brand': item.item.item.brand.name,
                        'item_name': item.item.item.item_name,
                        'model': item.item.item.model
                    }
                    for item in pending_items
                ]
            }

            return JsonResponse({
                'success': True,
                'redirect_url': reverse('purchasing:create_purchase_order')
            })
        except Exception as e:
            print(f"Error preparing PO data: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Error preparing purchase order data: {str(e)}'})

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Error processing request: {str(e)}'})

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
def purchase_order_list(request):
    """List all purchase orders and approved requisitions grouped by brand"""
    context = {
        'orders': PurchaseOrder.objects.all().order_by('-created_at'),
        'approved_items': RequisitionItem.objects.filter(
            requisition__status='pending_admin_approval'
        ).select_related(
            'item__brand',
            'requisition__requester'
        ).order_by('item__brand__name'),
        'suppliers': Supplier.objects.all(),
        'warehouses': Warehouse.objects.all(),
    }
    return render(request, 'purchasing/purchase_order_list.html', context)

@login_required
def remove_pending_item(request, pk):
    try:
        pending_item = get_object_or_404(PendingPOItem, id=pk)
        pending_item.delete()
        messages.success(request, "Item removed from pending items.")
    except Exception as e:
        messages.error(request, f"Error removing item: {str(e)}")
    return redirect('purchasing:pending_po_items')

@login_required
def clear_pending_items(request):
    """Clear all pending PO items for a specific brand"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'})

    try:
        data = json.loads(request.body)
        brand = data.get('brand')

        if not brand:
            return JsonResponse({'success': False, 'error': 'Brand is required'})

        # Get all pending requisitions with items of this brand
        requisitions = Requisition.objects.filter(
            status='pending_admin_approval',
            items__item__brand__name=brand
        ).distinct()
        
        # Update their status
        requisitions.update(status='rejected')

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def clear_brand_pending_items(request, brand_id):
    """Clear all pending PO items for a specific brand"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        # Get the brand object
        brand = get_object_or_404(Brand, name=brand_id)
        
        # Delete all pending items for this brand
        items_deleted = PendingPOItem.objects.filter(
            brand=brand,
            is_processed=False
        ).delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully cleared {items_deleted[0]} items for brand {brand.name}'
        })
        
    except Brand.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'Brand {brand_id} not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

@login_required
def pending_po_items(request):
    # Get all pending items that haven't been processed
    pending_items = PendingPOItem.objects.filter(is_processed=False)
    
    # Get all suppliers and warehouses for the form
    suppliers = Supplier.objects.all()
    warehouses = Warehouse.objects.filter(name__in=['Attendant Warehouse', 'Manager Warehouse'])
    
    context = {
        'pending_items': pending_items,
        'suppliers': suppliers,
        'warehouses': warehouses,
    }
    
    return render(request, 'purchasing/pending_po_items.html', context)

@login_required
def remove_pending_item(request, pk):
    try:
        pending_item = get_object_or_404(PendingPOItem, id=pk)
        pending_item.delete()
        messages.success(request, "Item removed from pending items.")
    except Exception as e:
        messages.error(request, f"Error removing item: {str(e)}")
    return redirect('purchasing:pending_po_items')