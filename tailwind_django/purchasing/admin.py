from django.contrib import admin
from .models import Supplier, PurchaseOrder, PurchaseOrderItem

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone')
    search_fields = ('name', 'contact_person', 'email')

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'status', 'order_date', 'total_amount')
    list_filter = ('status', 'supplier')
    search_fields = ('po_number', 'supplier__name')

@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'item', 'quantity', 'unit_price')
    search_fields = ('purchase_order__po_number', 'item__item_name')
    list_filter = ('purchase_order__status',)