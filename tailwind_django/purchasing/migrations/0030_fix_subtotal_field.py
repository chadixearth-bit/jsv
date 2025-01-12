from django.db import migrations, models

def calculate_subtotal(apps, schema_editor):
    PurchaseOrderItem = apps.get_model('purchasing', 'PurchaseOrderItem')
    for item in PurchaseOrderItem.objects.all():
        item.subtotal = item.quantity * item.unit_price
        item.save()

class Migration(migrations.Migration):

    dependencies = [
        ('purchasing', '0029_purchaseorderitem_item_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorderitem',
            name='subtotal',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(calculate_subtotal),
    ]
