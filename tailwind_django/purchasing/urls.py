from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    path('', views.PurchaseOrderListView.as_view(), name='list'),
    path('create/', views.create_purchase_order, name='create_purchase_order'),
    path('create/<int:requisition_id>/', views.create_purchase_order, name='create_purchase_order'),
    path('add-supplier/', views.SupplierCreateView.as_view(), name='add_supplier'),
    path('<int:pk>/add-items/', views.AddItemsView.as_view(), name='add_items'),
    path('<int:pk>/view/', views.view_purchase_order, name='view_po'),
    path('<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='edit_po'),
    path('<int:pk>/confirm/', views.confirm_purchase_order, name='confirm_purchase_order'),
    path('<int:po_pk>/delete-item/<int:item_pk>/', views.delete_item, name='delete_item'),
    path('<int:pk>/download-pdf/', views.download_po_pdf, name='download_pdf'),
    path('deliveries/', views.delivery_list, name='delivery_list'),
    path('deliveries/upcoming/', views.upcoming_deliveries, name='upcoming_deliveries'),
    path('delivery/<int:pk>/', views.view_delivery, name='view_delivery'),
    path('delivery/<int:pk>/confirm/', views.confirm_delivery, name='confirm_delivery'),
    path('delivery/<int:pk>/start/', views.start_delivery, name='start_delivery'),
    path('delivery/<int:pk>/receive/', views.receive_delivery, name='receive_delivery'),
    path('delivery/clear-history/', views.clear_delivery_history, name='clear_delivery_history'),
    # Shortcuts for easier access
    path('dl/', views.delivery_list, name='dl'),  # Short for delivery list
    path('ud/', views.upcoming_deliveries, name='ud'),  # Short for upcoming deliveries
]