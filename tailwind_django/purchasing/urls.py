from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    # Purchase Order List and Creation
    path('', views.PurchaseOrderListView.as_view(), name='list'),
    path('create/', views.PurchaseOrderCreateView.as_view(), name='create_purchase_order'),
    path('create/<int:requisition_id>/', views.create_purchase_order, name='create_purchase_order_with_requisition'),
    
    # Supplier Management
    path('add-supplier/', views.SupplierCreateView.as_view(), name='add_supplier'),
    
    # Purchase Order Management
    path('<int:pk>/add-items/', views.AddItemsView.as_view(), name='add_items'),
    path('<int:pk>/view/', views.view_purchase_order, name='view_purchase_order'),
    path('<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='edit_purchase_order'),
    path('<int:pk>/confirm/', views.confirm_purchase_order, name='confirm_purchase_order'),
    path('<int:po_pk>/delete-item/<int:item_pk>/', views.delete_item, name='delete_item'),
    path('<int:pk>/submit/', views.submit_purchase_order, name='submit_purchase_order'),
    path('<int:pk>/update-status/', views.update_po_status, name='update_po_status'),
    path('<int:pk>/download-pdf/', views.download_po_pdf, name='download_purchase_order_pdf'),
    path('clear-brand-items/', views.clear_brand_pending_items, name='clear_brand_items'),
    
    # Delivery Management
    path('deliveries/', views.delivery_list, name='delivery_list'),
    path('deliveries/upcoming/', views.upcoming_deliveries, name='upcoming_deliveries'),
    path('delivery/<int:pk>/', views.view_delivery, name='view_delivery'),
    path('delivery/<int:pk>/view/', views.view_delivery, name='view_delivery_detail'),
    path('delivery/<int:pk>/confirm/', views.confirm_delivery, name='confirm_delivery'),
    path('delivery/<int:pk>/start/', views.start_delivery, name='start_delivery'),
    path('delivery/<int:pk>/receive/', views.receive_delivery, name='receive_delivery'),
    path('delivery/<int:pk>/upload-image/', views.upload_delivery_image, name='upload_delivery_image'),
    path('delivery/clear-history/', views.clear_delivery_history, name='clear_delivery_history'),
    
    # Bulk Operations
    path('create-bulk-po/', views.create_bulk_po, name='create_bulk_po'),
    
    # Pending Items Management
    path('pending-items/', views.pending_po_items, name='pending_po_items'),
    path('create_po_from_pending/<str:brand>/', views.create_po_from_pending, name='create_po_from_pending'),
    path('clear_brand_pending_items/<str:brand_name>/', views.clear_brand_pending_items, name='clear_brand_pending_items'),
    path('remove_pending_item/<int:pk>/', views.remove_pending_item, name='remove_pending_item'),
    path('pending-items/clear/', views.clear_pending_items, name='clear_pending_items'),
    
    # Shortcuts
    path('dl/', views.delivery_list, name='delivery_list_shortcut'),
    path('ud/', views.upcoming_deliveries, name='upcoming_deliveries_shortcut'),
]