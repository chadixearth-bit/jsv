from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Case, When, IntegerField, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from io import BytesIO
from .models import Requisition, Notification, RequisitionItem, Delivery, DeliveryItem, RequisitionStatusHistory
from .forms import RequisitionForm, RequisitionApprovalForm, DeliveryManagementForm, DeliveryConfirmationForm
from inventory.models import InventoryItem, Warehouse, Brand, Category
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from django.conf import settings
import logging
import os
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_notification(requisition):
    """Create in-system notifications for relevant users"""
    # Create notification for managers first
    managers = User.objects.filter(customuser__role='manager')
    
    items = requisition.items.all()
    if items.exists():
        items_str = ', '.join([f"{item.item.item_name} (x{item.quantity})" for item in items])
        message = f'New requisition created for: {items_str} by {requisition.requester.username}'
    else:
        message = f'New requisition created by {requisition.requester.username}'

    for manager in managers:
        Notification.objects.create(
            user=manager,
            requisition=requisition,
            message=message
        )
    
    # Create notification for the requester with personalized message
    if requisition.requester.customuser.role == 'admin':
        message = f'Requisition has been created and is pending approval'
    else:
        message = f'Your requisition has been created and is pending approval'
        
    Notification.objects.create(
        user=requisition.requester,
        requisition=requisition,
        message=message
    )

def create_delivery_notification(delivery, action, user=None):
    """Create notifications for delivery actions"""
    requisition = delivery.requisition
    
    if action == 'started':
        message = f'Delivery has been started by manager {delivery.delivered_by.username}'
    elif action == 'confirmed_manager':
        message = f'Delivery has been confirmed by manager {user.username}'
    elif action == 'confirmed_attendant':
        message = f'Delivery has been confirmed by {user.username}'
    elif action == 'confirmed_admin':
        message = f'Delivery has been confirmed by admin {user.username}'
    elif action == 'confirmed_delivery':
        message = f'Delivery has been confirmed by manager {user.username}'
    else:
        return
        
    # Create notification for all involved parties
    for notify_user in [requisition.requester, delivery.delivered_by]:
        Notification.objects.create(
            user=notify_user,
            requisition=requisition,
            message=message
        )

@login_required(login_url='account:login')
def requisition_list(request):
    print("\n=== DEBUG: Requisition List ===")
    print(f"User: {request.user.username}")
    print(f"Role: {request.user.customuser.role if hasattr(request.user, 'customuser') else None}")
    
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    # Build the base queryset
    requisitions = Requisition.objects.select_related(
        'requester',
        'source_warehouse',
        'destination_warehouse'
    ).prefetch_related(
        'items',
        'items__item'
    )
    
    # Filter based on user role
    if user_role == 'attendant':
        # Attendants can only see their own requisitions
        requisitions = requisitions.filter(requester=request.user)
    elif user_role == 'manager':
        # Managers can see:
        # 1. Requisitions they created
        # 2. Requisitions from attendants where they are the destination warehouse
        user_warehouse = request.user.customuser.warehouses.first()
        requisitions = requisitions.filter(
            Q(requester=request.user) |  # Their own requisitions
            Q(destination_warehouse=user_warehouse, requester__customuser__role='attendant')  # Attendant requisitions to their warehouse
        )
    elif user_role == 'admin':
        # Admins can only see requisitions from managers
        requisitions = requisitions.filter(requester__customuser__role='manager')
    else:
        # If role not recognized, show no requisitions
        requisitions = requisitions.none()
    
    # Order by most recent first
    requisitions = requisitions.order_by('-created_at')
    
    print(f"\n=== DEBUG: Filtered Requisitions ===")
    print(f"Total requisitions: {requisitions.count()}")
    for req in requisitions:
        print(f"ID: {req.id}, Requester: {req.requester.username}, Role: {req.requester.customuser.role}")
    
    context = {
        'requisitions': requisitions,
        'user_role': user_role
    }
    return render(request, 'requisition/requisition_list.html', context)

@login_required
def create_requisition(request):
    # Debug logging
    print("\n=== DEBUG: Create Requisition ===")
    print(f"User: {request.user.username}")
    print(f"Role: {request.user.customuser.role if hasattr(request.user, 'customuser') else None}")
    
    # Get user's warehouse
    user_warehouse = request.user.customuser.warehouses.first() if hasattr(request.user, 'customuser') else None
    print(f"User Warehouse: {user_warehouse.name if user_warehouse else None}")
    
    if not user_warehouse:
        messages.error(request, "You must be assigned to a warehouse to create requisitions.")
        return redirect('requisition:requisition_list')
    
    # Fetch items for the user's warehouse
    if request.user.customuser.role == 'attendant':
        # Attendants can see all items from their warehouse, including 0 stock
        available_items = InventoryItem.objects.filter(
            warehouse=user_warehouse
        ).select_related('brand', 'category', 'warehouse')
    elif request.user.customuser.role == 'manager':
        # Managers can see items from their own warehouse
        available_items = InventoryItem.objects.filter(
            warehouse=user_warehouse
        ).select_related('brand', 'category', 'warehouse')
    else:
        available_items = InventoryItem.objects.none()
    
    print("\n=== DEBUG: Available Items ===")
    print(f"Total items: {available_items.count()}")
    for item in available_items:
        print(f"- {item.item_name} (ID: {item.id}, Stock: {item.stock}, Warehouse: {item.warehouse.name})")
    
    # Check if user has permission to create requisition
    if not hasattr(request.user, 'customuser') or request.user.customuser.role not in ['attendant', 'manager']:
        messages.error(request, "You don't have permission to create requisitions.")
        return redirect('requisition:requisition_list')
    
    if request.method == 'POST':
        print("\n=== DEBUG: Processing POST request ===")
        print(f"POST data: {request.POST}")
        
        # Get form data
        quantities = json.loads(request.POST.get('quantities', '{}'))
        reason = request.POST.get('reason', '')
        
        # Handle new item requests
        new_items_json = request.POST.get('new_items')
        new_items = []
        if new_items_json:
            try:
                new_items = json.loads(new_items_json)
                if not isinstance(new_items, list):
                    new_items = [new_items]  # Convert single object to list
            except json.JSONDecodeError:
                messages.error(request, "Invalid new items data format")
                return redirect('requisition:create_requisition')

        if not quantities and not new_items:
            messages.error(request, "Please select at least one item or request a new item")
            return redirect('requisition:create_requisition')

        form = RequisitionForm(request.POST, user=request.user)
        form.fields['items'].queryset = available_items  # Set the queryset for items field
        print(f"Form is valid: {form.is_valid()}")
        
        if not form.is_valid():
            print(f"\n=== DEBUG: Form Errors ===")
            for field, errors in form.errors.items():
                print(f"Field '{field}': {errors}")
                messages.error(request, f"{field}: {', '.join(errors)}")
            for error in form.non_field_errors():
                print(f"Non-field error: {error}")
                messages.error(request, error)
            return render(request, 'requisition/create_requisition.html', {
                'form': form,
                'available_items': available_items
            })
            
        try:
            with transaction.atomic():
                print("\n=== DEBUG: Creating Requisition ===")
                requisition = form.save(commit=False)
                requisition.requester = request.user
                requisition.request_type = 'item'  # Set default request type
                
                # Set status and warehouse based on user role
                if request.user.customuser.role == 'attendant':
                    print("\n=== DEBUG: Setting up attendant requisition ===")
                    requisition.status = 'pending'  # Pending manager approval
                    requisition.source_warehouse = user_warehouse
                    
                    # Find a manager's warehouse
                    manager_warehouse = Warehouse.objects.filter(
                        custom_users__role='manager'
                    ).exclude(
                        id=requisition.source_warehouse.id
                    ).first()
                    
                    if not manager_warehouse:
                        raise ValueError("No manager warehouse found. Please contact an administrator.")
                    
                    requisition.destination_warehouse = manager_warehouse
                    print(f"Source warehouse: {requisition.source_warehouse.name}")
                    print(f"Destination warehouse: {requisition.destination_warehouse.name}")
                
                elif request.user.customuser.role == 'manager':
                    requisition.status = 'pending_admin_approval'
                    requisition.source_warehouse = user_warehouse
                
                print("\n=== DEBUG: Saving requisition ===")
                print(f"Request type: {requisition.request_type}")
                print(f"Status: {requisition.status}")
                print(f"Source warehouse: {requisition.source_warehouse}")
                print(f"Destination warehouse: {requisition.destination_warehouse}")
                print(f"Requester: {requisition.requester}")
                
                requisition.save()
                
                # Handle existing items
                items = form.cleaned_data.get('items', [])
                quantities = json.loads(request.POST.get('quantities', '{}'))
                for item in items:
                    quantity = int(quantities.get(str(item.id), 0))
                    if quantity > 0:
                        RequisitionItem.objects.create(
                            requisition=requisition,
                            item=item,
                            quantity=quantity,
                            is_new_item=False  # Existing items are not new
                        )
                
                # Handle new item requests
                new_items_json = request.POST.get('new_items')
                if new_items_json:
                    try:
                        new_items = json.loads(new_items_json)
                        if not isinstance(new_items, list):
                            new_items = [new_items]  # Convert single object to list
                            
                        for new_item in new_items:
                            # Get or create the brand
                            brand_name = new_item.get('brand', '').strip()
                            if not brand_name:
                                brand_name = "Unknown Brand"
                            
                            brand, _ = Brand.objects.get_or_create(name=brand_name)
                            
                            # Get or create a default category if needed
                            category, _ = Category.objects.get_or_create(name="Uncategorized")
                            
                            # Create a placeholder inventory item for tracking
                            item = InventoryItem.objects.create(
                                item_name=new_item['item_name'],
                                model=new_item.get('model', 'N/A'),
                                brand=brand,
                                category=category,
                                warehouse=user_warehouse,
                                stock=0,  # New items start with 0 stock
                                price=0.00,  # Set a default price
                                availability=False  # Not available until approved
                            )
                            
                            # Create requisition item marked as new
                            RequisitionItem.objects.create(
                                requisition=requisition,
                                item=item,
                                quantity=new_item.get('quantity', 1),  # Get quantity or default to 1
                                is_new_item=True  # Mark as a new item request
                            )
                            
                            # Set requisition status to pending_admin_approval for new items
                            requisition.status = 'pending_admin_approval'
                            requisition.save()
                    except json.JSONDecodeError:
                        messages.error(request, "Invalid new items data format")
                        return redirect('requisition:create_requisition')
                    except KeyError as e:
                        messages.error(request, f"Missing required field: {str(e)}")
                        return redirect('requisition:create_requisition')
                
                # Create notification for the requisition
                create_notification(requisition)
                print("\n=== DEBUG: Notification created ===")

                messages.success(request, 'Requisition created successfully.')
                print("\n=== DEBUG: Redirecting to requisition list ===")
                return redirect('requisition:requisition_list')

        except json.JSONDecodeError:
            messages.error(request, "Invalid quantities format. Please try again.")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            print(f"\n=== DEBUG: Error creating requisition ===")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            print(f"Error details: {e}")
            messages.error(request, "An error occurred while creating the requisition. Please try again.")
        
        return render(request, 'requisition/create_requisition.html', {
            'form': form,
            'available_items': available_items
        })
    
    else:
        form = RequisitionForm(user=request.user)
        form.fields['items'].queryset = available_items
    
    return render(request, 'requisition/create_requisition.html', {
        'form': form,
        'available_items': available_items
    })

def edit_requisition(request, pk):
    requisition = get_object_or_404(Requisition, pk=pk)
    if not requisition.can_edit():
        messages.error(request, "You can't edit this requisition.")
        return redirect('requisition:requisition_list')

    if request.method == 'POST':
        form = RequisitionForm(request.POST, instance=requisition)
        if form.is_valid():
            form.save()
            messages.success(request, 'Requisition updated successfully.')
            return redirect('requisition:requisition_list')
    else:
        form = RequisitionForm(instance=requisition)

    return render(request, 'requisition/edit_requisition.html', {'form': form, 'requisition': requisition})

def reject_requisition(request, pk):
    requisition = get_object_or_404(Requisition, pk=pk)
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None

    if user_role not in ['admin', 'manager']:
        messages.error(request, "You don't have permission to reject requisitions.")
        return redirect('requisition:requisition_list')

    if request.method == 'POST':
        comment = request.POST.get('comment', '')
        try:
            with transaction.atomic():
                requisition.status = 'rejected'
                requisition.approval_comment = comment
                requisition.save()
                messages.success(request, 'Requisition rejected successfully.')
                return redirect('requisition:requisition_list')
        except Exception as e:
            messages.error(request, f"Error rejecting requisition: {str(e)}")
    
    return redirect('requisition:requisition_list')

@login_required
def approve_requisition(request, pk):
    requisition = get_object_or_404(Requisition, pk=pk)
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    # Only managers can approve requisitions
    if user_role != 'manager':
        messages.error(request, "Only managers can approve requisitions.")
        return redirect('requisition:requisition_list')
    
    # Cannot approve if already processed
    if requisition.status != 'pending':
        messages.error(request, "This requisition cannot be approved.")
        return redirect('requisition:requisition_list')
    
    form = RequisitionApprovalForm()
    
    # Get manager's warehouse
    manager_warehouse = request.user.customuser.warehouses.first()
    
    # Prepare items with availability info
    items_with_availability = []
    for req_item in requisition.items.all():
        # Check if this is a new item request
        is_new_item = req_item.item.is_new_item if hasattr(req_item.item, 'is_new_item') else False
        
        if is_new_item:
            # For new items, we don't check stock availability
            items_with_availability.append({
                'item': req_item,
                'is_new_item': True,
                'available_stock': 0,
                'stock': 0,
                'is_available': False,
                'is_partial': False,
                'has_sufficient_stock': False,
                'manager_warehouse': manager_warehouse.name
            })
        else:
            # Check availability in manager's warehouse for existing items
            manager_item = InventoryItem.objects.filter(
                warehouse=manager_warehouse,
                item_name__iexact=req_item.item.item_name
            ).first()
            
            available_stock = manager_item.stock if manager_item else 0
            requested_quantity = req_item.quantity
            
            items_with_availability.append({
                'item': req_item,
                'is_new_item': False,
                'available_stock': available_stock,
                'stock': available_stock,
                'is_available': available_stock >= requested_quantity,
                'is_partial': 0 < available_stock < requested_quantity,
                'has_sufficient_stock': available_stock >= requested_quantity,
                'manager_warehouse': manager_warehouse.name
            })
    
    if request.method == 'POST':
        form = RequisitionApprovalForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # For new items, we don't need to check stock
                    has_new_items = any(item['is_new_item'] for item in items_with_availability)
                    
                    if has_new_items:
                        # Set status to pending_admin for new item requests
                        requisition.status = 'pending_admin'
                        requisition.save()
                        messages.success(request, 'New item requisition forwarded to admin for review.')
                        return redirect('requisition:requisition_list')
                    
                    # For existing items, check stock availability
                    for req_item in requisition.items.all():
                        manager_item = InventoryItem.objects.filter(
                            warehouse=manager_warehouse,
                            item_name__iexact=req_item.item.item_name
                        ).first()
                        
                        if not manager_item:
                            raise ValueError(f"Item {req_item.item.item_name} not found in manager's warehouse")
                        
                        if manager_item.stock < req_item.quantity:
                            raise ValueError(f"Insufficient stock for {req_item.item.item_name}. Available: {manager_item.stock}, Requested: {req_item.quantity}")
                    
                    # All stock checks passed, proceed with approval
                    requisition.status = 'approved'
                    requisition.approved_by = request.user
                    requisition.approved_at = timezone.now()
                    requisition.save()
                    
                    # Create delivery record
                    delivery = Delivery.objects.create(
                        requisition=requisition,
                        status='pending_delivery'
                    )
                    
                    # Create delivery items
                    for req_item in requisition.items.all():
                        manager_item = InventoryItem.objects.get(
                            warehouse=manager_warehouse,
                            item_name__iexact=req_item.item.item_name
                        )
                        
                        DeliveryItem.objects.create(
                            delivery=delivery,
                            item=manager_item,
                            quantity=req_item.quantity
                        )
                    
                    # Update requisition with warehouse information
                    requisition.source_warehouse = manager_warehouse
                    requisition.destination_warehouse = req_item.item.warehouse
                    requisition.save()
                    
                    # Create notification
                    create_notification(requisition)
                    
                    messages.success(request, 'Requisition approved successfully.')
                    return redirect('requisition:requisition_list')
                    
            except ValueError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f"Error approving requisition: {str(e)}")
    
    return render(request, 'requisition/approve_requisition.html', {
        'requisition': requisition,
        'form': form,
        'items_with_availability': items_with_availability,
        'manager_warehouse': manager_warehouse
    })

def complete_requisition(request, pk):
    requisition = get_object_or_404(Requisition, pk=pk)
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None

    if user_role != 'admin':
        messages.error(request, "You don't have permission to complete requisitions.")
        return redirect('requisition:requisition_list')

    requisition.complete()
    
    # Create notification for requisition completion
    Notification.objects.create(
        user=requisition.requester,
        requisition=requisition,
        message=f'Your requisition has been marked as completed by admin {request.user.username}'
    )
    
    messages.success(request, 'Requisition completed successfully.')
    return redirect('requisition:requisition_list')

def delete_requisition(request, pk):
    """Permanently delete a requisition and all its related data."""
    requisition = get_object_or_404(Requisition, pk=pk)
    
    # Check if user has permission to delete
    if not request.user.is_superuser and request.user != requisition.requester:
        messages.error(request, "You don't have permission to delete this requisition.")
        return redirect('requisition:requisition_list')
    
    try:
        # Delete all related objects
        requisition.delete()
        messages.success(request, 'Requisition permanently deleted.')
    except Exception as e:
        messages.error(request, f'Error deleting requisition: {str(e)}')
    
    return redirect('requisition:requisition_list')

def delete_all_requisitions(request):
    """Permanently delete all requisitions for a user."""
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can delete all requisition history.")
        return redirect('requisition:requisition_history')
    
    if request.method != 'POST':
        return redirect('requisition:requisition_history')
    
    try:
        # Delete all requisitions
        Requisition.objects.all().delete()
        messages.success(request, 'All requisition history has been permanently deleted.')
    except Exception as e:
        messages.error(request, f'Error deleting requisitions: {str(e)}')
    
    return redirect('requisition:requisition_history')

@login_required(login_url='account:login')
def requisition_history(request):
    user = request.user
    user_role = user.customuser.role if hasattr(user, 'customuser') else None

    if not user_role:
        raise PermissionDenied("You don't have permission to view requisition history.")

    # Get filter parameters
    query = request.GET.get('q', '')
    status = request.GET.get('status', '')
    warehouse_id = request.GET.get('warehouse', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # Base queryset
    requisitions = Requisition.objects.all().order_by('-created_at')

    # Apply filters
    if query:
        requisitions = requisitions.filter(
            Q(id__icontains=query) |
            Q(requester__username__icontains=query) |
            Q(items__item__name__icontains=query) |
            Q(warehouse__name__icontains=query)
        ).distinct()

    if status:
        requisitions = requisitions.filter(status=status)

    if warehouse_id:
        requisitions = requisitions.filter(
            Q(source_warehouse_id=warehouse_id) | 
            Q(destination_warehouse_id=warehouse_id)
        )

    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d')
            requisitions = requisitions.filter(created_at__gte=date_from)
        except ValueError:
            messages.error(request, 'Invalid from date format')

    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire end date
            date_to = date_to + timedelta(days=1)
            requisitions = requisitions.filter(created_at__lt=date_to)
        except ValueError:
            messages.error(request, 'Invalid to date format')

    # Pagination
    paginator = Paginator(requisitions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Get all warehouses for the filter dropdown
    warehouses = Warehouse.objects.all()

    context = {
        'requisitions': page_obj,
        'query': query,
        'status': status,
        'warehouses': warehouses,
        'selected_warehouse': warehouse_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'requisition/requisition_history.html', context)

def delivery_list(request):
    print("\n=== DEBUG: Starting delivery_list ===")
    print(f"User: {request.user.username}")
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    print(f"User role: {user_role}")
    print(f"User's warehouses: {[w.name for w in request.user.customuser.warehouses.all()]}")

    # Filter deliveries based on user role
    if user_role == 'manager':
        # Get deliveries where source warehouse is one of the manager's warehouses
        manager_warehouses = request.user.customuser.warehouses.all()
        print(f"Manager warehouses: {[w.name for w in manager_warehouses]}")
        deliveries = Delivery.objects.filter(
            requisition__source_warehouse__in=manager_warehouses
        ).select_related(
            'requisition',
            'requisition__requester',
            'requisition__source_warehouse',
            'requisition__destination_warehouse',
            'delivered_by'
        ).prefetch_related('items__item__brand')
        print(f"Found deliveries: {[d.id for d in deliveries]}")
    elif user_role == 'attendant':
        deliveries = Delivery.objects.filter(
            Q(status='in_delivery') |
            Q(status='pending_delivery') |
            Q(status='delivered') |
            Q(status='pending_manager') |
            Q(status='received', delivery_date__gte=timezone.now() - timedelta(days=7))
        ).order_by(
            Case(
                When(status='in_delivery', then=0),
                When(status='pending_delivery', then=1),
                When(status='delivered', then=2),
                When(status='pending_manager', then=3),
                When(status='received', then=4),
                default=5,
                output_field=IntegerField(),
            ),
            '-delivery_date'
        ).select_related(
            'requisition',
            'requisition__requester',
            'requisition__source_warehouse',
            'requisition__destination_warehouse',
            'delivered_by'
        ).prefetch_related('items__item__brand')
    else:
        deliveries = Delivery.objects.none()

    status_filter = request.GET.get('status')
    if status_filter:
        deliveries = deliveries.filter(status=status_filter)

    # Prepare items data for each delivery
    for delivery in deliveries:
        items_data = []
        for item in delivery.items.all():
            items_data.append({
                'item_name': str(item.item.item_name),
                'brand': str(item.item.brand.name) if item.item.brand else '',
                'model': str(item.item.model or ''),
                'quantity': item.quantity
            })
        # Convert to JSON string and mark as safe
        delivery.items_json = json.dumps(items_data)
        print(f"DEBUG: Items JSON for delivery {delivery.id}: {delivery.items_json}")

    paginator = Paginator(deliveries, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'user_role': user_role,
        'status_filter': status_filter,
        'deliveries': {
            'pending_count': deliveries.filter(status='pending_delivery').count(),
            'in_progress_count': deliveries.filter(status='in_delivery').count()
        }
    }
    
    return render(request, 'requisition/delivery_list.html', context)

def manage_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    requisition = delivery.requisition
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    print("\n=== DEBUG: Managing Delivery ===")
    print(f"Delivery ID: {delivery.id}")
    print(f"User: {request.user.username}")
    print(f"User Role: {user_role}")
    print(f"Source Warehouse: {requisition.source_warehouse}")
    print(f"User's Warehouses: {[w.name for w in request.user.customuser.warehouses.all()]}")
    
    if user_role != 'manager':
        messages.error(request, "Only managers can start deliveries.")
        return redirect('requisition:delivery_list')

    if delivery.status != 'pending_delivery':
        messages.error(request, "This delivery cannot be started.")
        return redirect('requisition:delivery_list')

    # Get items from the source warehouse (manager's warehouse)
    source_warehouse = requisition.source_warehouse
    if not source_warehouse:
        messages.error(request, "No source warehouse set for this delivery.")
        return redirect('requisition:delivery_list')
        
    print(f"Checking warehouse access:")
    print(f"Source Warehouse ID: {source_warehouse.id}")
    print(f"User's Warehouse IDs: {[w.id for w in request.user.customuser.warehouses.all()]}")
    
    if source_warehouse not in request.user.customuser.warehouses.all():
        messages.error(request, "You don't have access to the source warehouse.")
        return redirect('requisition:delivery_list')

    if request.method == 'POST':
        try:
            estimated_delivery_date = request.POST.get('estimated_delivery_date')
            delivery_personnel_name = request.POST.get('delivery_personnel_name')
            delivery_personnel_phone = request.POST.get('delivery_personnel_phone')
            delivery_note = request.POST.get('delivery_note', '')  # Get delivery note
            
            if not all([estimated_delivery_date, delivery_personnel_name, delivery_personnel_phone]):
                messages.error(request, "Please fill in all required fields.")
                return redirect('requisition:manage_delivery', pk=pk)

            # Get all delivery items first to validate quantities
            items_to_process = []
            for delivery_item in delivery.items.all():
                quantity = request.POST.get(f'quantity_{delivery_item.id}')
                if not quantity:
                    messages.error(request, f"Please enter quantity for {delivery_item.item.item_name}")
                    return redirect('requisition:manage_delivery', pk=pk)
                
                try:
                    quantity = int(quantity)
                    source_item = InventoryItem.objects.get(
                        warehouse=source_warehouse,
                        item_name=delivery_item.item.item_name,
                        brand=delivery_item.item.brand,
                        model=delivery_item.item.model
                    )
                    
                    if quantity <= 0:
                        messages.error(request, f"Quantity must be greater than 0 for {delivery_item.item.item_name}")
                        return redirect('requisition:manage_delivery', pk=pk)
                    if quantity > source_item.stock:
                        messages.error(request, f"Not enough stock in {source_warehouse.name} for {delivery_item.item.item_name}. Available: {source_item.stock}")
                        return redirect('requisition:manage_delivery', pk=pk)
                    
                    items_to_process.append((delivery_item, source_item, quantity))
                    
                except ValueError:
                    messages.error(request, f"Invalid quantity for {delivery_item.item.item_name}")
                    return redirect('requisition:manage_delivery', pk=pk)
                except InventoryItem.DoesNotExist:
                    messages.error(request, f"Item {delivery_item.item.item_name} not found in {source_warehouse.name}")
                    return redirect('requisition:manage_delivery', pk=pk)

            # All validations passed, now process the delivery
            with transaction.atomic():
                # Update delivery information
                delivery.estimated_delivery_date = estimated_delivery_date
                delivery.delivery_personnel_name = delivery_personnel_name
                delivery.delivery_personnel_phone = delivery_personnel_phone
                delivery.status = 'in_delivery'
                delivery.delivered_by = request.user
                delivery.notes = delivery_note  # Add delivery note
                delivery.save()

                # Process each delivery item
                for delivery_item, source_item, quantity in items_to_process:
                    delivery_item.item = source_item
                    delivery_item.quantity = quantity
                    delivery_item.save()

                # Create notification
                create_delivery_notification(delivery, 'started')
                messages.success(request, 'Delivery has been started successfully.')
                return redirect('requisition:delivery_list')

        except Exception as e:
            messages.error(request, f"Error starting delivery: {str(e)}")
            return redirect('requisition:manage_delivery', pk=pk)

    # Get items from source warehouse for display
    delivery_items = []
    for delivery_item in delivery.items.all():
        try:
            source_item = InventoryItem.objects.get(
                warehouse=source_warehouse,
                item_name=delivery_item.item.item_name,
                brand=delivery_item.item.brand,
                model=delivery_item.item.model
            )
            delivery_items.append({
                'delivery_item': delivery_item,
                'item': source_item,
                'requested_quantity': delivery_item.quantity,
                'available_stock': source_item.stock
            })
        except InventoryItem.DoesNotExist:
            messages.warning(request, f"Item {delivery_item.item.item_name} not found in {source_warehouse.name}")

    context = {
        'delivery': delivery,
        'requisition': requisition,
        'delivery_items': delivery_items,
        'source_warehouse': source_warehouse,
        'user_role': user_role,
    }
    return render(request, 'requisition/manage_delivery.html', context)

def start_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    
    # Check if user is a manager
    if not request.user.customuser.role == 'manager':
        messages.error(request, "You don't have permission to start deliveries.")
        return redirect('requisition:delivery_list')
    
    # Check if delivery is in pending_delivery status
    if delivery.status != 'pending_delivery':
        messages.error(request, "This delivery cannot be started.")
        return redirect('requisition:delivery_list')
    
    try:
        with transaction.atomic():
            # Update delivery status
            delivery.status = 'in_delivery'
            delivery.save()
            
            # Create notification for attendant
            Notification.objects.create(
                user=delivery.requisition.requester,
                requisition=delivery.requisition,
                message=f'Your delivery has been started by manager {request.user.username}. Please confirm when received.'
            )
            
            messages.success(request, 'Delivery has been started.')
    except Exception as e:
        messages.error(request, f'Error starting delivery: {str(e)}')
    
    return redirect('requisition:delivery_list')

def confirm_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    if user_role == 'attendant':
        if 'delivery_image' not in request.FILES:
            messages.error(request, 'Please upload a delivery image.')
            return redirect('requisition:delivery_list')
        
        try:
            with transaction.atomic():
                # Save delivery image
                delivery.delivery_image = request.FILES['delivery_image']
                delivery.status = 'pending_manager'  
                delivery.delivery_date = timezone.now()
                delivery.save()
                
                # Create notification for manager
                Notification.objects.create(
                    user=delivery.delivered_by,
                    requisition=delivery.requisition,
                    message=f'Delivery has been confirmed by attendant {request.user.username}. Please verify the delivery image.'
                )
                
                messages.success(request, 'Delivery confirmation submitted. Awaiting manager verification.')
        except Exception as e:
            messages.error(request, f"Error confirming delivery: {str(e)}")
    
    elif user_role == 'manager':
        try:
            with transaction.atomic():
                # Manager verifying the delivery
                delivery.status = 'delivered'
                delivery.save()
                
                # Update requisition status to delivered
                requisition = delivery.requisition
                requisition.status = 'delivered'
                requisition.manager_comment = f'Delivery confirmed and verified by manager {request.user.username}'
                requisition.save()
                
                # Update inventory quantities
                for delivery_item in delivery.items.all():
                    # Deduct from source warehouse (manager's)
                    source_item = InventoryItem.objects.filter(
                        warehouse=delivery.requisition.source_warehouse,
                        item_name__iexact=delivery_item.item.item_name,
                        brand=delivery_item.item.brand,
                        model=delivery_item.item.model
                    ).first()
                    
                    if not source_item:
                        raise InventoryItem.DoesNotExist(f"Source item {delivery_item.item.item_name} not found in {delivery.requisition.source_warehouse.name}")
                    
                    if source_item.stock < delivery_item.quantity:
                        raise Exception(f"Insufficient stock for {delivery_item.item.item_name} in {delivery.requisition.source_warehouse.name}")
                    
                    source_item.stock -= delivery_item.quantity
                    source_item.save()
                    
                    # Add to destination warehouse (attendant's)
                    dest_item = InventoryItem.objects.filter(
                        warehouse=delivery.requisition.destination_warehouse,
                        item_name__iexact=delivery_item.item.item_name,
                        brand=delivery_item.item.brand,
                        model=delivery_item.item.model
                    ).first()
                    
                    if dest_item:
                        dest_item.stock += delivery_item.quantity
                        dest_item.save()
                    else:
                        # Create new item in destination warehouse if it doesn't exist
                        InventoryItem.objects.create(
                            warehouse=delivery.requisition.destination_warehouse,
                            item_name=delivery_item.item.item_name,
                            brand=delivery_item.item.brand,
                            model=delivery_item.item.model,
                            stock=delivery_item.quantity,
                            category=delivery_item.item.category,
                            description=delivery_item.item.description,
                            unit=delivery_item.item.unit,
                            reorder_level=delivery_item.item.reorder_level,
                            unit_price=delivery_item.item.unit_price
                        )
                
                # Create notification for attendant
                Notification.objects.create(
                    user=delivery.requisition.requester,
                    requisition=delivery.requisition,
                    message=f'Your delivery has been verified by manager {request.user.username}. Items have been added to your inventory.'
                )
                
                messages.success(request, 'Delivery has been verified and inventory has been updated.')
        except InventoryItem.DoesNotExist:
            messages.error(request, f'Error: Source item not found in inventory.')
        except Exception as e:
            messages.error(request, f'Error verifying delivery: {str(e)}')
    
    return redirect('requisition:delivery_list')

def get_delivery_details(request, pk):
    try:
        delivery = get_object_or_404(Delivery.objects.select_related(
            'requisition',
            'requisition__requester',
            'requisition__source_warehouse',
            'requisition__destination_warehouse',
            'delivered_by'
        ), pk=pk)
        
        # Prepare delivery data
        items_data = []
        try:
            delivery_items = delivery.items.select_related(
                'item', 'item__brand', 'item__category'
            ).all()
            
            for item in delivery_items:
                items_data.append({
                    'item_name': item.item.item_name,
                    'brand': item.item.brand.name if item.item.brand else 'N/A',
                    'category': item.item.category.name if item.item.category else 'N/A',
                    'quantity': item.quantity
                })
        except Exception as e:
            print(f"Error getting delivery items: {e}")
            items_data = []

        # Get personnel info
        personnel_name = delivery.delivery_personnel_name or (
            delivery.delivered_by.get_full_name() or delivery.delivered_by.username
        )
        contact_number = delivery.delivery_personnel_phone or 'N/A'

        # Get requester info
        requester = delivery.requisition.requester
        requester_name = requester.get_full_name() or requester.username
        
        data = {
            'id': f'DEL-{delivery.id:04d}',  # Format: DEL-0001
            'source_warehouse': delivery.requisition.source_warehouse.name,
            'destination_warehouse': delivery.requisition.destination_warehouse.name,
            'status': delivery.get_status_display(),
            'created_at': delivery.created_at.strftime('%B %d, %Y %H:%M') if delivery.created_at else None,
            'estimated_delivery_date': delivery.estimated_delivery_date.strftime('%B %d, %Y') if delivery.estimated_delivery_date else None,
            'delivery_personnel': personnel_name,
            'contact_number': contact_number,
            'requester': requester_name,  
            'items': items_data,
            'notes': delivery.notes or ''
        }
        
        return JsonResponse(data)
    except Delivery.DoesNotExist:
        return JsonResponse({'error': 'Delivery not found'}, status=404)
    except Exception as e:
        import traceback
        print(f"Error in get_delivery_details: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)

def view_delivery_pdf(request, pk):
    try:
        delivery = get_object_or_404(Delivery.objects.select_related(
            'requisition',
            'requisition__requester',
            'requisition__source_warehouse',
            'requisition__destination_warehouse',
            'delivered_by'
        ).prefetch_related('items__item__brand', 'items__item__category'), pk=pk)

        # Create the PDF document
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="delivery_{delivery.id}.pdf"'

        # Create the PDF object using ReportLab
        doc = SimpleDocTemplate(
            response,
            pagesize=letter,
            rightMargin=inch/2,
            leftMargin=inch/2,
            topMargin=inch/2,
            bottomMargin=inch/2
        )

        # Container for the 'Flowable' objects
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a56db'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        subheader_style = ParagraphStyle(
            'SubHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#4a5568'),
            spaceBefore=20,
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        detail_label_style = ParagraphStyle(
            'DetailLabel',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a5568'),
            fontName='Helvetica-Bold'
        )
        
        detail_value_style = ParagraphStyle(
            'DetailValue',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1a202c'),
            leftIndent=20
        )
        
        story = []
        
        # Add company header
        story.append(Paragraph("COMPANY NAME", header_style))
        story.append(Paragraph("Requisition Form", subheader_style))
        story.append(Spacer(1, 20))
        
        # Add horizontal line
        story.append(HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor('#e2e8f0'),
            spaceBefore=10,
            spaceAfter=20
        ))
        
        # Create two-column layout for requisition details
        data = [
            [Paragraph("<b>Requisition ID:</b>", detail_label_style),
             Paragraph(f"#{requisition.id}", detail_value_style),
             Paragraph("<b>Status:</b>", detail_label_style),
             Paragraph(requisition.get_status_display(), detail_value_style)],
            [Paragraph("<b>Requestor:</b>", detail_label_style),
             Paragraph(requisition.requester.get_full_name() or requisition.requester.username, detail_value_style),
             Paragraph("<b>Request Date:</b>", detail_label_style),
             Paragraph(requisition.created_at.strftime('%Y-%m-%d %H:%M') if requisition.created_at else None, detail_value_style)],
            [Paragraph("<b>Request Type:</b>", detail_label_style),
             Paragraph(requisition.get_request_type_display(), detail_value_style),
             Paragraph("<b>Created By:</b>", detail_label_style),
             Paragraph(requisition.requester.username, detail_value_style)]
        ]
        
        if requisition.source_warehouse:
            data.append([
                Paragraph("<b>Source Warehouse:</b>", detail_label_style),
                Paragraph(requisition.source_warehouse.name, detail_value_style),
                Paragraph("<b>Destination Warehouse:</b>", detail_label_style),
                Paragraph(requisition.destination_warehouse.name if requisition.destination_warehouse else "-", detail_value_style)
            ])
        
        # Create the details table
        details_table = Table(data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a202c')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
        ]))
        story.append(details_table)
        story.append(Spacer(1, 20))
        
        # Add reason section
        story.append(Paragraph("Reason for Request", styles['Heading3']))
        story.append(Paragraph(requisition.reason, detail_value_style))
        story.append(Spacer(1, 20))
        
        # Create items table
        story.append(Paragraph("Requested Items", styles['Heading3']))
        story.append(Spacer(1, 15))
        if requisition.items.exists():
            # Only show delivered quantity if delivery has started
            has_delivery = Delivery.objects.filter(requisition=requisition).exists() and requisition.status in ['in_delivery', 'received']
            headers = ['Item Name', 'Brand', 'Model', 'Quantity']
            if has_delivery:
                headers.insert(3, 'Delivered Quantity')
            
            items_data = [headers]
            
            for req_item in requisition.items.all():
                row = [
                    req_item.item.item_name,
                    req_item.item.brand.name if req_item.item.brand else 'N/A',
                    req_item.item.model if hasattr(req_item.item, 'model') else 'N/A',
                    str(req_item.quantity)
                ]
                if has_delivery:
                    row.insert(3, str(req_item.delivered_quantity or 0))
                items_data.append(row)
                
            # Calculate column widths based on content type
            if has_delivery:
                col_widths = [3.5*inch, 1.5*inch, 1.5*inch, 1.2*inch, 1.2*inch]  # Adjusted for 5 columns
            else:
                col_widths = [4*inch, 1.8*inch, 1.8*inch, 1.4*inch]  # Adjusted for 4 columns
            
            # Create and style the table with the new column widths
            table = Table(items_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a202c')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # Add manager comment if exists
        if requisition.manager_comment:
            story.append(Spacer(1, 20))
            story.append(Paragraph("Manager's Comment", styles['Heading3']))
            story.append(Paragraph(requisition.manager_comment, detail_value_style))
        
        # Add footer
        story.append(Spacer(1, 40))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} | Requisition #{requisition.id}"
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER
        )
        story.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Return PDF response
        if os.path.exists(filepath):
            with open(filepath, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="delivery_{delivery.id}.pdf"'
                return response
            
    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect('requisition:requisition_list')
    finally:
        # Clean up the temporary PDF file
        if 'filepath' in locals() and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

def get_requisition_details(request, pk):
    requisition = get_object_or_404(Requisition, pk=pk)
    
    # Prepare items data
    items_data = []
    for item in requisition.items.all():
        image_url = None
        if item.item.image:
            try:
                image_url = request.build_absolute_uri(item.item.image.url)
            except Exception as e:
                print(f"Error getting image URL: {e}")
        
        items_data.append({
            'name': item.item.item_name,
            'brand': item.item.brand.name if item.item.brand else 'N/A',
            'quantity': item.quantity,
            'delivered_quantity': item.delivered_quantity if item.delivered_quantity else None,
            'image_url': image_url
        })
    
    data = {
        'id': requisition.id,
        'status': requisition.get_status_display(),
        'created_at': requisition.created_at.strftime('%Y-%m-%d %H:%M') if requisition.created_at else None,
        'requester': requisition.requester.get_full_name() or requisition.requester.username,
        'items': items_data,
        'reason': requisition.reason,
        'manager_comment': requisition.manager_comment,
        'request_type': requisition.get_request_type_display(),
        'source_warehouse': requisition.source_warehouse.name if requisition.source_warehouse else None,
        'destination_warehouse': requisition.destination_warehouse.name if requisition.destination_warehouse else None,
    }
    
    return JsonResponse(data)

def get_warehouse_items(request, warehouse_id):
    """API endpoint to get items for a specific warehouse with stock > 0"""
    try:
        logger.info(f"Fetching items for warehouse ID: {warehouse_id}")
        items = InventoryItem.objects.filter(
            warehouse_id=warehouse_id
        ).select_related(
            'warehouse', 'brand'
        ).values(
            'id', 'item_name', 'stock', 'model',
            'warehouse__name', 'brand__name'
        )
        logger.info(f"Number of items fetched: {len(items)}")
        return JsonResponse(list(items), safe=False)
    except Exception as e:
        logger.error(f"Error fetching items: {str(e)}")
        return JsonResponse({'error': f"Error fetching items: {str(e)}"}, status=400)

def search_items(request):
    """API endpoint to search for items"""
    query = request.GET.get('q', '').strip()
    if not query:  
        return JsonResponse({'error': 'Query is required'}, status=400)

    logger.info('Search items called with parameters: %s', request.GET)
    # Get the user's warehouses
    user_warehouses = request.user.customuser.warehouses.all()
    if not user_warehouses.exists():
        return JsonResponse({'error': 'No warehouse assigned'}, status=400)

    # Search for items that match the query and belong to user's warehouses
    items = InventoryItem.objects.filter(
        warehouse__in=user_warehouses
    ).filter(
        Q(item_name__icontains=query) |
        Q(brand__name__icontains=query)
    ).select_related('warehouse', 'brand')[:10]  

    logger.info('Items found: %s', items)
    
    if not items:
        logger.warning('No items found for query: %s', query)
        return JsonResponse({'error': 'No items found'}, status=400)

    results = []
    for item in items:
        results.append({
            'id': item.id,
            'item_name': item.item_name,
            'brand': item.brand.name if item.brand else 'N/A',
            'stock': item.stock,
            'warehouse': item.warehouse.name if item.warehouse else 'N/A'
        })

    return JsonResponse(results, safe=False)

def view_requisition_pdf(request, pk):
    try:
        # Get the requisition object
        requisition = get_object_or_404(Requisition, pk=pk)
        
        # Create the directory if it doesn't exist
        pdf_dir = os.path.join(settings.MEDIA_ROOT, 'requisition_pdfs')
        os.makedirs(pdf_dir, exist_ok=True)

        # Generate filename
        filename = f"requisition_{requisition.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(pdf_dir, filename)

        # Create the PDF document with custom margins
        doc = SimpleDocTemplate(
            filepath,
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        header_style = ParagraphStyle(
            'CustomHeader',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a56db'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        subheader_style = ParagraphStyle(
            'SubHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#4a5568'),
            spaceBefore=20,
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        detail_label_style = ParagraphStyle(
            'DetailLabel',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#4a5568'),
            fontName='Helvetica-Bold'
        )
        
        detail_value_style = ParagraphStyle(
            'DetailValue',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1a202c'),
            leftIndent=20
        )
        
        story = []
        
        # Add company header
        story.append(Paragraph("COMPANY NAME", header_style))
        story.append(Paragraph("Requisition Form", subheader_style))
        story.append(Spacer(1, 20))
        
        # Add horizontal line
        story.append(HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor('#e2e8f0'),
            spaceBefore=10,
            spaceAfter=20
        ))
        
        # Create two-column layout for requisition details
        data = [
            [Paragraph("<b>Requisition ID:</b>", detail_label_style),
             Paragraph(f"#{requisition.id}", detail_value_style),
             Paragraph("<b>Status:</b>", detail_label_style),
             Paragraph(requisition.get_status_display(), detail_value_style)],
            [Paragraph("<b>Requestor:</b>", detail_label_style),
             Paragraph(requisition.requester.get_full_name() or requisition.requester.username, detail_value_style),
             Paragraph("<b>Request Date:</b>", detail_label_style),
             Paragraph(requisition.created_at.strftime('%Y-%m-%d %H:%M') if requisition.created_at else None, detail_value_style)],
            [Paragraph("<b>Request Type:</b>", detail_label_style),
             Paragraph(requisition.get_request_type_display(), detail_value_style),
             Paragraph("<b>Created By:</b>", detail_label_style),
             Paragraph(requisition.requester.username, detail_value_style)]
        ]
        
        if requisition.source_warehouse:
            data.append([
                Paragraph("<b>Source Warehouse:</b>", detail_label_style),
                Paragraph(requisition.source_warehouse.name, detail_value_style),
                Paragraph("<b>Destination Warehouse:</b>", detail_label_style),
                Paragraph(requisition.destination_warehouse.name if requisition.destination_warehouse else "-", detail_value_style)
            ])
        
        # Create the details table
        details_table = Table(data, colWidths=[1.5*inch, 2*inch, 1.5*inch, 2*inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#ffffff')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a202c')),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
        ]))
        story.append(details_table)
        story.append(Spacer(1, 20))
        
        # Add reason section
        story.append(Paragraph("Reason for Request", styles['Heading3']))
        story.append(Paragraph(requisition.reason, detail_value_style))
        story.append(Spacer(1, 20))
        
        # Create items table
        story.append(Paragraph("Requested Items", styles['Heading3']))
        story.append(Spacer(1, 15))
        if requisition.items.exists():
            # Only show delivered quantity if delivery has started
            has_delivery = Delivery.objects.filter(requisition=requisition).exists() and requisition.status in ['in_delivery', 'received']
            headers = ['Item Name', 'Brand', 'Model', 'Quantity']
            if has_delivery:
                headers.insert(3, 'Delivered Quantity')
            
            items_data = [headers]
            
            for req_item in requisition.items.all():
                row = [
                    req_item.item.item_name,
                    req_item.item.brand.name if req_item.item.brand else 'N/A',
                    req_item.item.model if hasattr(req_item.item, 'model') else 'N/A',
                    str(req_item.quantity)
                ]
                if has_delivery:
                    row.insert(3, str(req_item.delivered_quantity or 0))
                items_data.append(row)
                
            # Calculate column widths based on content type
            if has_delivery:
                col_widths = [3.5*inch, 1.5*inch, 1.5*inch, 1.2*inch, 1.2*inch]  # Adjusted for 5 columns
            else:
                col_widths = [4*inch, 1.8*inch, 1.8*inch, 1.4*inch]  # Adjusted for 4 columns
            
            # Create and style the table with the new column widths
            table = Table(items_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a56db')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('TOPPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1a202c')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(table)
            story.append(Spacer(1, 15))
        
        # Add manager comment if exists
        if requisition.manager_comment:
            story.append(Spacer(1, 20))
            story.append(Paragraph("Manager's Comment", styles['Heading3']))
            story.append(Paragraph(requisition.manager_comment, detail_value_style))
        
        # Add footer
        story.append(Spacer(1, 40))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')} | Requisition #{requisition.id}"
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#718096'),
            alignment=TA_CENTER
        )
        story.append(Paragraph(footer_text, footer_style))
        
        # Build PDF
        doc.build(story)
        
        # Return PDF response
        if os.path.exists(filepath):
            with open(filepath, 'rb') as pdf_file:
                response = HttpResponse(pdf_file.read(), content_type='application/pdf')
                response['Content-Disposition'] = 'inline; filename="{}"'.format(filename)
                return response
            
    except Exception as e:
        messages.error(request, f"Error generating PDF: {str(e)}")
        return redirect('requisition:requisition_list')
    finally:
        # Clean up the temporary PDF file
        if 'filepath' in locals() and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass

@login_required
def view_requisition(request, pk):
    """
    View details of a specific requisition
    """
    requisition = get_object_or_404(Requisition.objects.select_related(
        'requester',
        'source_warehouse',
        'destination_warehouse'
    ).prefetch_related(
        'items',
        'items__item'
    ), pk=pk)
    
    # Check if user has permission to view this requisition
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    if user_role == 'attendant':
        # Attendants can only view their own requisitions
        if requisition.requester != request.user:
            raise PermissionDenied
    elif user_role == 'manager':
        # Managers can view:
        # 1. Their own requisitions
        # 2. Requisitions from attendants where they are the destination warehouse manager
        user_warehouse = request.user.customuser.warehouses.first()
        if not (requisition.requester == request.user or 
                (requisition.destination_warehouse == user_warehouse and 
                 requisition.requester.customuser.role == 'attendant')):
            raise PermissionDenied
    elif user_role == 'admin':
        # Admins can only view requisitions from managers
        if requisition.requester.customuser.role != 'manager':
            raise PermissionDenied
    else:
        raise PermissionDenied
    
    context = {
        'requisition': requisition,
        'user_role': user_role
    }
    return render(request, 'requisition/view_requisition.html', context)