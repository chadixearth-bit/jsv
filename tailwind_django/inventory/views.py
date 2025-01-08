from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Sum, Count
from django.db import transaction
from django.contrib.auth.decorators import login_required

from .models import InventoryItem, Brand, Category, Warehouse, GlobalSettings
from .forms import InventoryItemForm, BrandForm, CategoryForm, GlobalSettingsForm

@login_required(login_url='account:login')
def inventory_list(request):
    # Get user's role
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    # Get or create global settings
    global_settings = GlobalSettings.objects.first()
    if not global_settings:
        global_settings = GlobalSettings.objects.create()
    
    # Handle Global Settings form
    if request.method == 'POST' and request.user.customuser.role == 'manager':
        global_settings_form = GlobalSettingsForm(request.POST, instance=global_settings)
        if global_settings_form.is_valid():
            global_settings_form.save()
            messages.success(request, 'Global settings updated successfully.')
    else:
        global_settings_form = GlobalSettingsForm(instance=global_settings)
    
    # Base queryset
    queryset = InventoryItem.objects.all().select_related('warehouse', 'brand', 'category')
    
    # Filter by warehouse based on role, but show all items for admin
    if not request.user.is_superuser:  # Only filter for non-admin users
        if user_role == 'attendant':
            queryset = queryset.filter(warehouse_id=1)  # Attendant Warehouse (ID: 1)
        elif user_role == 'manager':
            queryset = queryset.filter(warehouse_id=2)  # Manager Warehouse (ID: 2)
    
    # Search functionality
    query = request.GET.get('q')
    if query:
        queryset = queryset.filter(
            Q(item_name__icontains=query) |
            Q(model__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Sorting
    sort_by = request.GET.get('sort')
    if sort_by == 'name':
        queryset = queryset.order_by('item_name')
    elif sort_by == 'brand':
        queryset = queryset.order_by('brand__name')
    elif sort_by == 'category':
        queryset = queryset.order_by('category__name')
    elif sort_by == 'stock':
        queryset = queryset.order_by('stock')
    
    # Filter handling
    selected_warehouse = request.GET.get('warehouse')
    selected_brand = request.GET.get('brand')
    selected_category = request.GET.get('category')
    filter_type = request.GET.get('filter', 'all')
    
    if selected_warehouse:
        queryset = queryset.filter(warehouse_id=selected_warehouse)
    if selected_brand:
        queryset = queryset.filter(brand_id=selected_brand)
    if selected_category:
        queryset = queryset.filter(category_id=selected_category)
    
    # Apply quick filters
    if filter_type == 'low_stock':
        queryset = queryset.filter(stock__lte=global_settings.reorder_level)
    elif filter_type == 'no_price':
        queryset = queryset.filter(Q(price__isnull=True) | Q(price=0))
    
    # Get all brands and categories for filters
    brands = Brand.objects.all()
    categories = Category.objects.all()
    warehouses = Warehouse.objects.all()
    
    # Count total items and items needing reorder
    total_items = queryset.count()
    reorder_needed = queryset.filter(stock__lte=global_settings.reorder_level).count()
    
    # Pagination
    paginator = Paginator(queryset, 10)
    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    
    context = {
        'items': items,
        'brands': brands,
        'categories': categories,
        'warehouses': warehouses,
        'global_settings_form': global_settings_form,
        'global_settings': global_settings,
        'selected_warehouse': selected_warehouse,
        'selected_brand': selected_brand,
        'selected_category': selected_category,
        'filter_type': filter_type,
        'total_items': total_items,
        'reorder_needed': reorder_needed,
        'query': query,
        'sort_by': sort_by,
        'user_role': user_role,
        'is_main_warehouse': user_role == 'manager' or request.user.is_superuser,
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
        form = InventoryItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Get the form data
                    create_in_both = form.cleaned_data.get('create_in_both', False)
                    warehouse = form.cleaned_data['warehouse']
                    
                    # Create base item data
                    item_data = {
                        'brand': form.cleaned_data['brand'],
                        'category': form.cleaned_data['category'],
                        'model': form.cleaned_data['model'],
                        'item_name': form.cleaned_data['item_name'],
                        'price': form.cleaned_data['price'],
                        'stock': form.cleaned_data['stock']
                    }
                    
                    # Handle image if provided
                    if form.cleaned_data.get('image'):
                        item_data['image'] = form.cleaned_data['image']

                    if create_in_both:
                        # Create in both warehouses
                        attendant_warehouse = Warehouse.objects.get(name='Attendant Warehouse')
                        manager_warehouse = Warehouse.objects.get(name='Manager Warehouse')
                        
                        # Create items in both warehouses
                        InventoryItem.objects.create(
                            warehouse=attendant_warehouse,
                            **item_data
                        )
                        InventoryItem.objects.create(
                            warehouse=manager_warehouse,
                            **item_data
                        )
                        messages.success(request, 'Item created successfully in both warehouses.')
                    else:
                        # Create item in the selected warehouse
                        InventoryItem.objects.create(
                            warehouse=warehouse,
                            **item_data
                        )
                        messages.success(request, f'Item created successfully in {warehouse.name}.')
                    
                    return redirect('inventory:list')
            except Exception as e:
                messages.error(request, f'Error creating item: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = InventoryItemForm(user=request.user)
    
    return render(request, 'inventory/inventory_form.html', {'form': form})

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
    # Get the manager warehouse
    manager_warehouse = Warehouse.objects.get(name='Manager Warehouse')
    items = InventoryItem.objects.filter(warehouse=manager_warehouse).select_related('warehouse', 'brand', 'category')
    
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
    # Get warehouse items based on user role
    user_role = request.user.customuser.role if hasattr(request.user, 'customuser') else None
    
    if user_role == 'admin':
        items = InventoryItem.objects.all()
    elif user_role == 'manager':
        manager_warehouse = Warehouse.objects.get(name='Manager Warehouse')
        items = InventoryItem.objects.filter(warehouse=manager_warehouse)
    elif user_role == 'attendant':
        attendant_warehouse = Warehouse.objects.get(name='Attendant Warehouse')
        items = InventoryItem.objects.filter(warehouse=attendant_warehouse)
    else:
        items = InventoryItem.objects.none()
    
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