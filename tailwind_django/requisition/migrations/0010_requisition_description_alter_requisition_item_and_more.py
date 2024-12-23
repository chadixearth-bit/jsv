# Generated by Django 5.1.3 on 2024-11-16 16:37

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_globalsettings_inventoryitem_description_and_more'),
        ('requisition', '0009_requisition_actual_delivery_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='requisition',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='requisition',
            name='item',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.inventoryitem'),
        ),
        migrations.AlterField(
            model_name='requisition',
            name='request_type',
            field=models.CharField(choices=[('item', 'Item Request'), ('service', 'Service Request')], default='item', max_length=10),
        ),
        migrations.AlterField(
            model_name='requisition',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('approved_by_manager', 'Approved by Manager'), ('rejected_by_manager', 'Rejected by Manager'), ('pending_admin_approval', 'Pending Admin Approval'), ('approved_by_admin', 'Approved by Admin'), ('rejected_by_admin', 'Rejected by Admin'), ('in_delivery', 'In Delivery'), ('delivered', 'Delivered')], default='pending', max_length=25),
        ),
    ]
