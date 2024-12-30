from django.db import migrations

def populate_warehouse(apps, schema_editor):
    Delivery = apps.get_model('purchasing', 'Delivery')
    for delivery in Delivery.objects.all():
        if delivery.warehouse_id is None and delivery.purchase_order_id is not None:
            delivery.warehouse = delivery.purchase_order.warehouse
            delivery.save()

class Migration(migrations.Migration):
    dependencies = [
        ('purchasing', '0013_remove_delivery_receipt_signature_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_warehouse),
    ]
