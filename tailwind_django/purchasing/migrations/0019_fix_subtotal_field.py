from django.db import migrations, models

def forwards_func(apps, schema_editor):
    # We're going to use the historical version of the model
    PurchaseOrderItem = apps.get_model("purchasing", "PurchaseOrderItem")
    db_alias = schema_editor.connection.alias

    # Update existing records to have subtotal = quantity * unit_price
    for item in PurchaseOrderItem.objects.using(db_alias).all():
        item.subtotal = item.quantity * item.unit_price
        item.save()

class Migration(migrations.Migration):
    dependencies = [
        ('purchasing', '0018_auto_20250104_1350'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorderitem',
            name='subtotal',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.RunPython(forwards_func),
    ]
