from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    path('', views.PurchaseOrderListView.as_view(), name='list'),
    path('create/', views.PurchaseOrderCreateView.as_view(), name='create_purchase_order'),
    path('create/<int:requisition_id>/', views.create_purchase_order, name='create_purchase_order_with_requisition'),
    path('create-po-from-requisition/<int:requisition_id>/', views.create_po_from_requisition, name='create_po_from_requisition'),
    path('add-supplier/', views.SupplierCreateView.as_view(), name='add_supplier'),
    path('<int:pk>/add-items/', views.AddItemsView.as_view(), name='add_items'),
    path('<int:pk>/view/', views.view_purchase_order, name='view_purchase_order'),
    path('<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='edit_purchase_order'),
    path('<int:pk>/confirm/', views.confirm_purchase_order, name='confirm_purchase_order'),
    path('<int:po_pk>/delete-item/<int:item_pk>/', views.delete_item, name='delete_item'),
    path('<int:pk>/download-pdf/', views.download_po_pdf, name='download_purchase_order_pdf'),
    path('deliveries/', views.delivery_list, name='delivery_list'),
    path('deliveries/upcoming/', views.upcoming_deliveries, name='upcoming_deliveries'),
    path('delivery/<int:pk>/', views.view_delivery, name='view_delivery'),
    path('delivery/<int:pk>/confirm/', views.confirm_delivery, name='confirm_delivery'),
    path('delivery/<int:pk>/start/', views.start_delivery, name='start_delivery'),
    path('delivery/<int:pk>/receive/', views.receive_delivery, name='receive_delivery'),
    path('delivery/<int:pk>/upload-image/', views.upload_delivery_image, name='upload_delivery_image'),
    path('delivery/clear-history/', views.clear_delivery_history, name='clear_delivery_history'),
    path('create-bulk-po/', views.create_bulk_po, name='create_bulk_po'),
    path('pending-items/<int:item_id>/remove/', views.remove_pending_item, name='remove_pending_item'),
    path('pending-items/clear/', views.clear_pending_items, name='clear_pending_items'),
    path('create-po/', views.create_po_from_pending, name='create_po_from_pending'),
    # Shortcuts for easier access
    path('dl/', views.delivery_list, name='delivery_list_shortcut'),  # Short for delivery list
    path('ud/', views.upcoming_deliveries, name='upcoming_deliveries_shortcut'),  # Short for upcoming deliveries
]