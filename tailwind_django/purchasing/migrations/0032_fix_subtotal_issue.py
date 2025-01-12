from django.db import migrations

def forwards_func(apps, schema_editor):
    # We're going to use the historical version of the model
    PurchaseOrderItem = apps.get_model("purchasing", "PurchaseOrderItem")
    db_alias = schema_editor.connection.alias
    
    # If the subtotal column exists, we'll keep it. If it doesn't, we'll create it.
    try:
        schema_editor.execute(
            "SELECT subtotal FROM purchasing_purchaseorderitem LIMIT 1"
        )
    except Exception:
        # Column doesn't exist, so we'll add it
        schema_editor.execute(
            "ALTER TABLE purchasing_purchaseorderitem ADD COLUMN subtotal numeric(10,2) DEFAULT 0"
        )

def reverse_func(apps, schema_editor):
    # No reverse operation needed
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('purchasing', '0031_remove_purchaseorderitem_subtotal'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
