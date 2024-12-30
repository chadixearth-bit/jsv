from django.urls import path
from . import views
from django.conf.urls.static import static

app_name = 'inventory'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('items/', views.inventory_list, name='list'),
    path('<int:pk>/', views.inventory_detail, name='detail'),
    path('create/', views.inventory_create, name='create'),
    path('<int:pk>/update/', views.inventory_update, name='update'),
    path('<int:pk>/delete/', views.inventory_delete, name='delete'),
    path('brand/create/', views.create_brand, name='create_brand'),
    path('category/create/', views.create_category, name='create_category'),
    path('<int:pk>/set-price/', views.set_price, name='set_price'),
    path('store/', views.store_inventory, name='store_inventory'),
    path('warehouse/', views.warehouse_inventory, name='warehouse_inventory'),
]