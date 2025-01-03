# Generated by Django 5.1.4 on 2025-01-03 03:51

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('purchasing', '0015_alter_delivery_warehouse'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='delivery',
            name='warehouse',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='receipt_photo',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='delivery_confirmation_file',
        ),
        migrations.RemoveField(
            model_name='delivery',
            name='notes',
        ),
        migrations.AlterField(
            model_name='delivery',
            name='status',
            field=models.CharField(choices=[('pending_delivery', 'Pending Delivery'), ('pending_confirmation', 'Pending Confirmation'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled')], default='pending_delivery', max_length=50),
        ),
        migrations.AddField(
            model_name='delivery',
            name='delivery_image',
            field=models.ImageField(blank=True, null=True, upload_to='delivery_images/%Y/%m/%d/'),
        ),
        migrations.AddField(
            model_name='delivery',
            name='delivery_note',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='delivery',
            name='confirmed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='confirmed_deliveries', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='delivery',
            name='confirmed_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='delivery',
            name='received_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='delivery',
            name='delivery_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
