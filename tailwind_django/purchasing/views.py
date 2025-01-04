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
from inventory.models import InventoryItem, Brand
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
    success_url = reverse_lazy('purchasing:list')

    def dispatch(self, request, *args, **kwargs) -> Any:
        if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
            messages.error(request, "Only admin users can create purchase orders.")
            return redirect('purchasing:list')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self) -> Dict:
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs: Any) -> Dict:
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Purchase Order'
        context['pending_requisitions'] = Requisition.objects.filter(
            request_type='item',
            status='approved_by_admin',
            items__item__stock=0
        ).distinct()
        context['available_items'] = InventoryItem.objects.select_related(
            'brand', 
            'category'
        ).filter(
            stock__lte=10
        ).order_by('brand__name', 'model', 'item_name')
        return context

    def form_valid(self, form: PurchaseOrderForm) -> Any:
        try:
            with transaction.atomic():
                po = form.save(commit=False)
                po.created_by = self.request.user
                po.status = 'pending_supplier'  # Automatically set to pending_supplier instead of draft
                po.save()

                # Handle existing items
                items = self.request.POST.getlist('items[]')
                quantities = self.request.POST.getlist('quantities[]')
                unit_prices = self.request.POST.getlist('unit_prices[]')

                for item_id, qty, price in zip(items, quantities, unit_prices):
                    if item_id and qty and price:  # Skip empty selections
                        item = InventoryItem.objects.get(id=item_id)
                        PurchaseOrderItem.objects.create(
                            purchase_order=po,
                            item=item,
                            quantity=int(qty),
                            unit_price=Decimal(price)
                        )

<<<<<<< Updated upstream
                # Handle new items
                new_items_name = self.request.POST.getlist('new_items[][name]')
                new_items_brand = self.request.POST.getlist('new_items[][brand]')
                new_items_model = self.request.POST.getlist('new_items[][model_name]')
                new_items_qty = self.request.POST.getlist('new_items[][quantity]')
                new_items_price = self.request.POST.getlist('new_items[][unit_price]')

                for name, brand_name, model, qty, price in zip(new_items_name, new_items_brand, new_items_model, new_items_qty, new_items_price):
                    if name and brand_name and qty and price:  # Skip empty entries
=======
                # Process new items
                new_items_data = zip(
                    self.request.POST.getlist('new_item_names[]'),
                    self.request.POST.getlist('new_brands[]'),
                    self.request.POST.getlist('new_models[]'),
                    self.request.POST.getlist('new_quantities[]'),
                    self.request.POST.getlist('new_unit_prices[]')
                )

                for name, brand_name, model_name, qty, price in new_items_data:
                    if all([name, brand_name, model_name, qty, price]):  # Skip if any field is empty
>>>>>>> Stashed changes
                        # Get or create brand
                        brand, _ = Brand.objects.get_or_create(name=brand_name)
                        
                        # Create new inventory item
                        new_item = InventoryItem.objects.create(
                            item_name=name,
                            brand=brand,
<<<<<<< Updated upstream
                            model=model,
                            stock=0,  # Initial stock is 0
                            price=Decimal(price),
                            category_id=1  # Default category
                        )
                        
=======
                            model=model_name,
                            availability=True
                        )

>>>>>>> Stashed changes
                        # Create purchase order item
                        PurchaseOrderItem.objects.create(
                            purchase_order=po,
                            item=new_item,
<<<<<<< Updated upstream
=======
                            brand=brand_name,
                            model_name=model_name,
>>>>>>> Stashed changes
                            quantity=int(qty),
                            unit_price=Decimal(price)
                        )

                po.calculate_total()
                messages.success(self.request, 'Purchase Order created and submitted for supplier approval.')
                return super().form_valid(form)

        except Exception as e:
            messages.error(self.request, f'Error creating purchase order: {str(e)}')
            return super().form_invalid(form)

    def form_invalid(self, form: PurchaseOrderForm) -> Any:
        messages.error(self.request, 'Error creating purchase order.')
        return self.render_to_response(self.get_context_data(form=form))

class PurchaseOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchasing/purchase_order_form.html'
    success_url = reverse_lazy('purchasing:list')

    def dispatch(self, request, *args, **kwargs):
        po = self.get_object()
        if po.status != 'draft':
            messages.error(request, "Only draft purchase orders can be edited.")
            return redirect('purchasing:list')
        if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'admin':
            messages.error(request, "Only admin users can edit purchase orders.")
            return redirect('purchasing:list')
        return super().dispatch(request, *args, **kwargs)

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
        context['items'] = self.object.items.all()
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
    po = get_object_or_404(PurchaseOrder.objects.select_related(
        'supplier',
        'warehouse',
        'created_by',
        'delivery_verified_by'
    ).prefetch_related(
        'items__item',
        'deliveries'
    ), pk=pk)
    
    # Check user permissions
    if not hasattr(request.user, 'customuser'):
        messages.error(request, "You don't have permission to view purchase orders.")
        return redirect('purchasing:list')
    
    user_role = request.user.customuser.role
    can_view = False
    
    if user_role == 'admin':
        can_view = True
    elif user_role in ['manager', 'attendant']:
        can_view = po.warehouse in request.user.warehouses.all()
    
    if not can_view:
        messages.error(request, "You don't have permission to view this purchase order.")
        return redirect('purchasing:list')
    
    # Get available status changes for the user
    available_status_changes = []
    for status_choice in PurchaseOrder.STATUS_CHOICES:
        if po.can_change_status(request.user, status_choice[0]):
            available_status_changes.append(status_choice)
    
    context = {
        'po': po,
        'items': po.items.all().select_related('item'),
        'deliveries': po.deliveries.all(),
        'available_status_changes': available_status_changes,
        'user_role': user_role
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
                        
                        # Get or create inventory item in the receiving warehouse
                        inventory_item, created = InventoryItem.objects.get_or_create(
                            warehouse=delivery.warehouse,
                            brand=po_item.item.brand,
                            model=po_item.item.model,
                            item_name=po_item.item.item_name,
                            defaults={
                                'category': po_item.item.category,
                                'stock': 0,
                                'price': 0,  # Set initial price to 0 as requested
                                'availability': True
                            }
                        )
                        
                        # Update stock quantity
                        inventory_item.stock += delivery_item.quantity_delivered
                        inventory_item.save()
                    
                    delivery.status = 'verified'
                    delivery.save()
                    
                    # Update PO status to completed
                    po.status = 'completed'
                    po.save()
                    
                    messages.success(request, 'Delivery confirmed successfully. Inventory quantities have been updated.')
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
        'warehouse',
        'received_by'
    ).prefetch_related(
        'items',
        'items__purchase_order_item',
        'items__purchase_order_item__item',
        'purchase_order__requisitions'
    )
    
    # Filter deliveries based on user role
    if hasattr(request.user, 'customuser'):
        user_role = request.user.customuser.role
        if user_role == 'admin':
            # Admin sees all deliveries
            deliveries = all_deliveries
        elif user_role in ['manager', 'attendant']:
            # Managers and attendants see deliveries to their warehouses
            user_warehouses = request.user.customuser.warehouses.all()
            deliveries = all_deliveries.filter(
                Q(warehouse__in=user_warehouses) |  # Deliveries to their warehouse
                Q(purchase_order__warehouse__in=user_warehouses)  # PO deliveries to their warehouse
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
        ('in_delivery', 'In Delivery'),
        ('pending_admin_confirmation', 'Pending Admin Confirmation'),
        ('verified', 'Verified'),
        ('cancelled', 'Cancelled')
    ]
    
    context = {
        'deliveries': deliveries,
        'current_time': timezone.now(),
        'current_status': status_filter or 'all',
        'status_choices': status_choices,
    }
    return render(request, 'purchasing/delivery_list.html', context)

@login_required
def view_delivery(request, pk: int) -> Any:
    delivery = get_object_or_404(Delivery.objects.select_related(
        'purchase_order',
        'purchase_order__supplier',
        'warehouse',
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
            if not (delivery.warehouse in user_warehouses or 
                   (delivery.purchase_order and delivery.purchase_order.warehouse in user_warehouses)):
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
            delivery.status = 'pending_admin_confirmation'
            delivery.save()
            messages.success(request, "Delivery receipt uploaded successfully. Awaiting admin confirmation.")
            return redirect('purchasing:view_delivery', pk=pk)
    else:
        form = DeliveryReceiptForm(instance=delivery)
    
    context = {
        'delivery': delivery,
        'form': form,
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
            warehouse=po.warehouse,  # Associate with the correct warehouse
            status='in_delivery'  # Changed to in_delivery since we can't track supplier
        )
        print(f"Created delivery {delivery.pk}")
        print(f"Delivery warehouse: {delivery.warehouse.name if delivery.warehouse else 'None'}")
        
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
        Q(warehouse__in=user_warehouses) |
        Q(warehouse__isnull=True, purchase_order__warehouse__in=user_warehouses),
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
def create_purchase_order(request):
    # Get requisition_id from query params
    requisition_id = request.GET.get('requisition_id')
    requisition = None
    
    if requisition_id:
        requisition = get_object_or_404(Requisition, pk=requisition_id)
        if requisition.status != 'approved_by_admin':
            messages.error(request, "This requisition has not been approved by admin.")
            return redirect('purchasing:list')

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create the purchase order
                    po = form.save(commit=False)
                    po.created_by = request.user
                    po.status = 'draft'
                    po.save()

                    if requisition:
                        # Add requisition to purchase order
                        po.requisitions.add(requisition)
                        
                        # Get unit prices from the form
                        unit_prices = request.POST.getlist('unit_prices[]')
                        
                        # Create purchase order items from requisition items
                        for index, req_item in enumerate(requisition.items.all()):
                            try:
                                unit_price = Decimal(unit_prices[index])
                            except (IndexError, ValueError, TypeError):
                                unit_price = Decimal('0')
                                
                            PurchaseOrderItem.objects.create(
                                purchase_order=po,
                                item=req_item.item,
                                quantity=req_item.quantity,
                                unit_price=unit_price,
                                brand=req_item.item.brand.name if req_item.item.brand else '',
                                model_name=req_item.item.model or ''
                            )
                    else:
                        # Handle existing items
                        items = request.POST.getlist('items[]')
                        quantities = request.POST.getlist('quantities[]')
                        unit_prices = request.POST.getlist('unit_prices[]')
                        
                        for item_id, qty, price in zip(items, quantities, unit_prices):
                            if item_id and qty and price:  # Skip empty selections
                                item = InventoryItem.objects.get(id=item_id)
                                PurchaseOrderItem.objects.create(
                                    purchase_order=po,
                                    item=item,
                                    quantity=int(qty),
                                    unit_price=Decimal(price),
                                    brand=item.brand.name if item.brand else '',
                                    model_name=item.model or ''
                                )

                    po.calculate_total()
                    messages.success(request, 'Purchase order created successfully.')
                    return redirect('purchasing:view_po', pk=po.id)
            except Exception as e:
                messages.error(request, f'Error creating purchase order: {str(e)}')
    else:
        initial_data = {}
        if requisition:
            initial_data['warehouse'] = requisition.source_warehouse
        form = PurchaseOrderForm(initial=initial_data)

    # Get available items for selection
    available_items = InventoryItem.objects.select_related('brand').all()

    return render(request, 'purchasing/purchase_order_form.html', {
        'form': form,
        'requisition': requisition,
        'available_items': available_items,
        'title': 'Create Purchase Order'
    })