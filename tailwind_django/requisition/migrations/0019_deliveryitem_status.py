# Generated by Django 5.1.3 on 2024-12-05 18:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('requisition', '0018_delivery_deliveryitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='deliveryitem',
            name='status',
            field=models.CharField(default='pending', max_length=20),
        ),
    ]