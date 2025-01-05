from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count

from .models import InventoryItem, Brand, Category, Warehouse, GlobalSettings
from .forms import InventoryItemForm, BrandForm, CategoryForm, GlobalSettingsForm

def inventory_list(request):
    # Get user role
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    # Handle Global Settings form
    global_settings = GlobalSettings.objects.first()
    if not global_settings:
        global_settings = GlobalSettings.objects.create()
    
    if request.method == 'POST' and user_role == 'admin':
        global_settings_form = GlobalSettingsForm(request.POST, instance=global_settings)
        if global_settings_form.is_valid():
            global_settings_form.save()
            messages.success(request, 'Global reorder level updated successfully.')
            return redirect('inventory:list')
    else:
        global_settings_form = GlobalSettingsForm(instance=global_settings)
    
    # Base query with related fields
    items = InventoryItem.objects.all().select_related('warehouse', 'brand', 'category')
    
    # Filter based on user role and set warehouse type
    is_main_warehouse = False
    if user_role == 'admin':
        # Admin sees all items
        pass
    elif user_role == 'manager':
        # Manager sees items in manager warehouse
        items = items.filter(location='manager_warehouse')
        is_main_warehouse = True
    elif user_role == 'attendant':
        # Attendant sees items in attendant warehouse
        items = items.filter(location='attendant_warehouse')
        is_main_warehouse = False
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        items = items.filter(
            Q(item_name__icontains=query) |
            Q(model__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Filter handling
    selected_warehouse = request.GET.get('warehouse')
    selected_brand = request.GET.get('brand')
    selected_category = request.GET.get('category')
    filter_type = request.GET.get('filter', 'all')
    
    if selected_warehouse:
        items = items.filter(warehouse_id=selected_warehouse)
    if selected_brand:
        items = items.filter(brand_id=selected_brand)
    if selected_category:
        items = items.filter(category_id=selected_category)
    
    # Get all brands and categories for filters
    brands = Brand.objects.all()
    categories = Category.objects.all()
    warehouses = Warehouse.objects.all()
    
    # Apply quick filters
    if filter_type == 'low_stock':
        items = items.filter(stock__lte=global_settings.reorder_level)
    elif filter_type == 'no_price':
        items = items.filter(Q(price__isnull=True) | Q(price=0))
    
    # Count total items and items needing reorder
    total_items = items.count()
    reorder_needed = items.filter(stock__lte=global_settings.reorder_level).count()
    
    # Pagination
    paginator = Paginator(items, 10)
    page = request.GET.get('page')
    items = paginator.get_page(page)
    
    context = {
        'items': items,
        'brands': brands,
        'categories': categories,
        'warehouses': warehouses,
        'is_main_warehouse': is_main_warehouse,
        'global_settings_form': global_settings_form,
        'global_settings': global_settings,
        'selected_warehouse': selected_warehouse,
        'selected_brand': selected_brand,
        'selected_category': selected_category,
        'filter_type': filter_type,
        'total_items': total_items,
        'reorder_needed': reorder_needed,
        'search_query': query
    }
    
    return render(request, 'inventory/inventory_list.html', context)

def inventory_detail(request, pk):
    item = get_object_or_404(
        InventoryItem.objects.select_related('warehouse', 'brand', 'category')
        .annotate(
            total_stock=Sum('stock'),
        ),
        pk=pk
    )
    context = {
        'item': item,
        'title': f'Item Details - {item.item_name}',
    }
    return render(request, 'inventory/inventory_detail.html', context)

def inventory_create(request):
    if request.method == 'POST':
        form = InventoryItemForm(request.POST, request.FILES)
        if form.is_valid():
            # Check if item already exists in the warehouse
            item_name = form.cleaned_data['item_name']
            model = form.cleaned_data['model']
            warehouse_choice = form.cleaned_data['warehouse_choice']
            
            # Convert warehouse_choice to location value
            location_mapping = {
                'attendant': 'attendant_warehouse',
                'manager': 'manager_warehouse',
            }
            location = location_mapping.get(warehouse_choice)
            
            # Query to check if the item already exists
            if InventoryItem.objects.filter(item_name=item_name, model=model, location=location).exists():
                messages.error(request, 'Error: This item is already in the warehouse.')
            else:
                result = form.save()
                
                if isinstance(result, list):
                    messages.success(request, 'Item created successfully in both warehouses.')
                else:
                    messages.success(request, 'Item created successfully.')
                
                return redirect('inventory:list')
        else:
            messages.error(request, 'Error creating item. Please check the form.')
    else:
        form = InventoryItemForm()
    
    return render(request, 'inventory/inventory_form.html', {'form': form, 'action': 'Create'})

def inventory_update(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    
    if request.method == 'POST':
        form = InventoryItemForm(request.POST, request.FILES, instance=item, user=request.user)
        if form.is_valid():
            try:
                updated_item = form.save(commit=False)
                if 'image' in request.FILES:
                    updated_item.image = request.FILES['image']
                updated_item.save()
                messages.success(request, 'Item updated successfully.')
                return redirect('inventory:list')
            except Exception as e:
                messages.error(request, f'Error updating item: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InventoryItemForm(instance=item, user=request.user)
    
    context = {
        'form': form,
        'action': 'Update',
        'title': 'Update Item',
        'item': item
    }
    return render(request, 'inventory/inventory_form.html', context)

def inventory_delete(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    
    if request.method == 'POST':
        if request.user.customuser.role == 'admin':
            # For admin, delete all items with same name and model
            InventoryItem.objects.filter(
                item_name=item.item_name,
                model=item.model
            ).delete()
            messages.success(request, 'Item deleted successfully from all warehouses.')
        else:
            # For non-admin users, just delete the specific item
            item.delete()
            messages.success(request, 'Item deleted successfully.')
        return redirect('inventory:list')
    
    # For GET request, show confirmation page
    return render(request, 'inventory/inventory_confirm_delete.html', {'item': item})

def create_brand(request):
    if request.method == 'POST':
        form = BrandForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Brand created successfully!')
            return redirect('inventory:list')
    else:
        form = BrandForm()
    return render(request, 'inventory/brand_form.html', {'form': form})

def create_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('inventory:list')
    else:
        form = CategoryForm()
    return render(request, 'inventory/category_form.html', {'form': form})

def set_price(request, pk):
    item = get_object_or_404(InventoryItem, pk=pk)
    
    if request.method == 'POST':
        try:
            new_price = request.POST.get('price')
            if new_price is not None:
                item.price = new_price
                item.save()
                messages.success(request, f'Price for {item.item_name} set successfully.')
            else:
                messages.error(request, 'Price value is required.')
        except ValueError:
            messages.error(request, 'Invalid price value.')
        return redirect('inventory:list')
    
    return render(request, 'inventory/set_price.html', {'item': item})

def store_inventory(request):
    # Debug logging
    print("\n=== DEBUG: Store Inventory ===")
    print(f"User: {request.user.username}")
    print(f"Role: {request.user.customuser.role if hasattr(request.user, 'customuser') else None}")
    
    # Get user's warehouse
    user_warehouse = request.user.customuser.warehouses.first() if hasattr(request.user, 'customuser') else None
    print(f"User Warehouse: {user_warehouse.name if user_warehouse else None}")
    
    # Get items in user's warehouse
    if user_warehouse:
        items = InventoryItem.objects.filter(warehouse=user_warehouse)
        print("\nItems in warehouse:")
        for item in items:
            print(f"- {item.item_name} (Stock: {item.stock})")
        print(f"Total items: {items.count()}")
    
    # Get all warehouses for debugging
    all_warehouses = Warehouse.objects.all()
    print("\nAll Warehouses:")
    for warehouse in all_warehouses:
        warehouse_items = InventoryItem.objects.filter(warehouse=warehouse)
        print(f"- {warehouse.name}: {warehouse_items.count()} items")
        print(f"  Users: {', '.join([u.username for u in warehouse.custom_users.all()])}")
    
    # Original function logic
    if not hasattr(request.user, 'customuser') or request.user.customuser.role != 'attendant':
        messages.error(request, "You don't have permission to view the store inventory.")
        return redirect('inventory:list')
    
    items = InventoryItem.objects.filter(
        warehouse=request.user.customuser.warehouses.first()
    ).select_related('brand', 'category')
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        items = items.filter(
            Q(item_name__icontains=query) |
            Q(model__icontains=query) |
            Q(brand__name__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(items, 10)
    page = request.GET.get('page')
    items = paginator.get_page(page)
    
    return render(request, 'inventory/store_inventory.html', {
        'items': items,
        'search_query': query
    })

def warehouse_inventory(request):
    """View for warehouse inventory (manager view)"""
    # Get all warehouses with manager role
    manager_warehouses = Warehouse.objects.filter(custom_users__role='manager')
    items = InventoryItem.objects.filter(warehouse__in=manager_warehouses).select_related('warehouse', 'brand', 'category')
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        items = items.filter(
            Q(item_name__icontains=query) |
            Q(model__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Get global settings
    global_settings, created = GlobalSettings.objects.get_or_create()
    
    context = {
        'items': items,
        'global_settings': global_settings,
        'view_type': 'warehouse'
    }
    
    return render(request, 'inventory/inventory_list.html', context)

def dashboard(request):
    # Get warehouse items
    items = InventoryItem.objects.all()
    
    # Calculate statistics
    total_items = items.count()
    total_value = items.aggregate(total=Sum('price'))['total'] or 0
    categories_count = Category.objects.count()
    
    # Get low stock items
    global_settings = GlobalSettings.objects.first()
    reorder_level = global_settings.reorder_level if global_settings else 2
    low_stock_items = items.filter(stock__lte=reorder_level)
    low_stock_count = low_stock_items.count()
    
    context = {
        'total_items': total_items,
        'total_value': total_value,
        'categories_count': categories_count,
        'low_stock_items': low_stock_items,
        'low_stock_count': low_stock_count,
    }
    
    return render(request, 'inventory/dashboard.html', context)