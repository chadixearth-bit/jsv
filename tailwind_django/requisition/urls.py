from django.urls import path
from . import views

app_name = 'requisition'

urlpatterns = [
    path('create/', views.create_requisition, name='create_requisition'),
    path('list/', views.requisition_list, name='requisition_list'),
    path('edit/<int:pk>/', views.edit_requisition, name='edit_requisition'),
    path('requisition/<int:pk>/', views.view_requisition, name='view_requisition'),
    path('requisition/<int:pk>/approve/', views.approve_requisition, name='approve_requisition'),
    path('requisition/<int:pk>/admin-approve/', views.admin_approve_requisition, name='admin_approve_requisition'),
    path('requisition/<int:pk>/reject/', views.reject_requisition, name='reject_requisition'),
    path('requisition/<int:pk>/delete/', views.delete_requisition, name='delete_requisition'),
    path('requisition/<int:pk>/pdf/', views.view_requisition_pdf, name='download_requisition_pdf'),
    path('requisition/get-details/<int:pk>/', views.get_requisition_details, name='get_requisition_details'),
    path('history/', views.requisition_history, name='requisition_history'),
    path('delivery/manage/<int:pk>/', views.manage_delivery, name='manage_delivery'),
    path('delivery/start/<int:pk>/', views.start_delivery, name='start_delivery'),
    path('delivery/confirm/<int:pk>/', views.confirm_delivery, name='confirm_delivery'),
    path('delivery/list/', views.delivery_list, name='delivery_list'),
    path('delivery/<int:pk>/details/', views.get_delivery_details, name='get_delivery_details'),
    path('delivery/<int:pk>/pdf/', views.view_delivery_pdf, name='view_delivery_pdf'),
    path('delivery/send-to-manager/<int:pk>/', views.send_to_manager, name='send_to_manager'),
    path('requisitions/delete-all/', views.delete_all_requisitions, name='delete_all_requisitions'),
    path('api/warehouse/<int:warehouse_id>/items/', views.get_warehouse_items, name='get_warehouse_items'),
    path('api/search-items/', views.search_items, name='search_items'),
]