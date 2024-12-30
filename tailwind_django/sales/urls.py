from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.sale_list, name='sale_list'),  # URL for listing sales
    path('create/', views.create_sale, name='create_sale'),  # URL for creating a sale
    path('receipt/<int:sale_id>/', views.download_receipt, name='download_receipt'),  # URL for downloading receipt
    path('return/<int:sale_id>/', views.return_sale, name='return_sale'),  # URL for returning a sale
]