from django.shortcuts import render, redirect
from .models import Sale, SaleItem, ReturnItem
from .forms import SaleForm
from django.contrib import messages
from inventory.models import InventoryItem, Brand, Category
from django.db.models import Q
from django.contrib.auth.models import User
from django.conf import settings
from .utils import generate_sale_receipt
from django.http import HttpResponse
import os
from decimal import Decimal
from django.utils import timezone
from django.db import models
from .recommendations import get_product_recommendations
import json

def sale_list(request):
    sales = Sale.objects.all().order_by('-sale_date')
    
    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        sales = sales.filter(
            Q(transaction_id__icontains=search_query) |
            Q(buyer__first_name__icontains=search_query) |
            Q(items__item__item_name__icontains=search_query)
        ).distinct()
    
    # Handle return status filter
    return_status = request.GET.get('return_status', '')
    if return_status == 'returned':
        sales = sales.filter(is_returned=True)
    elif return_status == 'not_returned':
        sales = sales.filter(is_returned=False)
    
    return render(request, 'sales/sale_list.html', {
        'sales': sales,
        'search_query': search_query,
        'return_status': return_status
    })

def create_sale(request):
    search_query = request.GET.get('search_query', '')
    brand_id = request.GET.get('brand')
    category_id = request.GET.get('category')
    selected_item_id = request.GET.get('selected_item')

    # Start with all available items
    items_queryset = InventoryItem.objects.all()

    # Apply filters
    if search_query:
        items_queryset = items_queryset.filter(
            Q(item_name__icontains=search_query) |
            Q(brand__name__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(model__icontains=search_query)
        )

    if brand_id:
        items_queryset = items_queryset.filter(brand_id=brand_id)

    if category_id:
        items_queryset = items_queryset.filter(category_id=category_id)

    # Get recommendations if an item is selected
    recommendations = []
    selected_item = None
    if selected_item_id:
        try:
            selected_item = InventoryItem.objects.get(id=selected_item_id)
            recommendations = get_product_recommendations(selected_item_id)
        except InventoryItem.DoesNotExist:
            pass

    context = {
        'items_queryset': items_queryset,
        'all_brands': Brand.objects.all(),
        'all_categories': Category.objects.all(),
        'recommendations': recommendations,
        'selected_item': selected_item,
    }

    if request.method == 'POST':
        # Handle sale creation
        selected_items = json.loads(request.POST.get('selected_items', '{}'))
        if not selected_items:
            messages.error(request, 'Please select at least one item')
            return render(request, 'sales/sale_form.html', context)

        try:
            sale = Sale.objects.create(
                sold_by=request.user,
                total_amount=sum(item['total'] for item in selected_items.values())
            )

            # Create sale items
            for item_id, item_data in selected_items.items():
                inventory_item = InventoryItem.objects.get(id=item_id)
                SaleItem.objects.create(
                    sale=sale,
                    item=inventory_item,
                    quantity=item_data['quantity'],
                    price=item_data['price']
                )
                # Update stock
                inventory_item.stock -= item_data['quantity']
                inventory_item.save()

            messages.success(request, 'Sale created successfully')
            return redirect('sales:sale_list')

        except Exception as e:
            messages.error(request, f'Error creating sale: {str(e)}')
            return render(request, 'sales/sale_form.html', context)

    return render(request, 'sales/sale_form.html', context)

def return_sale(request, sale_id):
    try:
        sale = Sale.objects.get(pk=sale_id)
        
        if request.method == 'POST':
            item_id = request.POST.get('item_id')
            return_quantity = int(request.POST.get('return_quantity', 0))
            return_reason = request.POST.get('return_reason', '')
            
            if not item_id or return_quantity <= 0:
                messages.error(request, 'Please select an item and specify a valid return quantity.')
                return redirect('sales:sale_list')
            
            try:
                sale_item = sale.items.get(id=item_id)
                total_returned = sale_item.returns.aggregate(
                    total=models.Sum('quantity'))['total'] or 0
                remaining_quantity = sale_item.quantity - total_returned
                
                if return_quantity > remaining_quantity:
                    messages.error(request, f'Cannot return more than {remaining_quantity} items.')
                    return redirect('sales:sale_list')
                
                ReturnItem.objects.create(
                    sale_item=sale_item,
                    quantity=return_quantity,
                    reason=return_reason
                )
                
                messages.success(request, f'Successfully returned {return_quantity} item(s).')
            except SaleItem.DoesNotExist:
                messages.error(request, 'Invalid item selected.')
            
        else:
            # Show return form
            return render(request, 'sales/return_form.html', {
                'sale': sale,
                'items': [
                    {
                        'id': item.id,
                        'name': str(item),
                        'remaining': item.quantity - (item.returns.aggregate(
                            total=models.Sum('quantity'))['total'] or 0)
                    }
                    for item in sale.items.all()
                ]
            })
            
    except Sale.DoesNotExist:
        messages.error(request, 'Sale not found.')
    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
    
    return redirect('sales:sale_list')

def download_receipt(request, sale_id):
    try:
        sale = Sale.objects.get(id=sale_id)
        receipt_filename = generate_sale_receipt(sale)
        file_path = os.path.join(settings.MEDIA_ROOT, 'receipts', receipt_filename)
        
        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{receipt_filename}"'
                return response
        
        messages.error(request, "Receipt file not found.")
        return redirect('sales:sale_list')
        
    except Sale.DoesNotExist:
        messages.error(request, "Sale not found.")
        return redirect('sales:sale_list')
