# Generated by Django 5.1.4 on 2024-12-12 20:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("purchasing", "0011_alter_purchaseorderitem_brand_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="delivery",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending_delivery", "Pending Delivery"),
                    ("in_transit", "In Transit"),
                    ("in_delivery", "In Delivery"),
                    ("delivered", "Delivered"),
                    ("pending_admin_confirmation", "Pending Admin Confirmation"),
                    ("verified", "Verified"),
                    ("completed", "Completed"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending_delivery",
                max_length=30,
            ),
        ),
    ]
