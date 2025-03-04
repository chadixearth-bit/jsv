# Generated by Django 5.1.4 on 2025-01-11 11:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requisition', '0034_delivery_destination_warehouse_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='requisition',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('pending_admin_approval', 'Pending Admin Approval'), ('approved_by_admin', 'Approved by Admin'), ('approved', 'Approved'), ('partially_approved', 'Partially Approved'), ('forwarded_to_admin', 'Forwarded to Admin'), ('rejected', 'Rejected'), ('pending_delivery', 'Pending Delivery'), ('in_delivery', 'In Delivery'), ('received', 'Received'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('pending_po', 'Pending Purchase Order')], default='pending', max_length=25),
        ),
        migrations.AlterField(
            model_name='requisitionstatushistory',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('pending_admin_approval', 'Pending Admin Approval'), ('approved_by_admin', 'Approved by Admin'), ('approved', 'Approved'), ('partially_approved', 'Partially Approved'), ('forwarded_to_admin', 'Forwarded to Admin'), ('rejected', 'Rejected'), ('pending_delivery', 'Pending Delivery'), ('in_delivery', 'In Delivery'), ('received', 'Received'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'), ('pending_po', 'Pending Purchase Order')], max_length=25),
        ),
    ]
