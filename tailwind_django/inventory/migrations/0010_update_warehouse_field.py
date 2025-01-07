from django.db import migrations, models
import django.db.models.deletion

def set_default_warehouse(apps, schema_editor):
    InventoryItem = apps.get_model('inventory', 'InventoryItem')
    Warehouse = apps.get_model('inventory', 'Warehouse')
    
    # Get or create the default warehouse
    default_warehouse, _ = Warehouse.objects.get_or_create(
        name='Attendant Warehouse',
        defaults={'is_main': False}
    )
    
    # Update all items without a warehouse
    InventoryItem.objects.filter(warehouse__isnull=True).update(warehouse=default_warehouse)

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0009_remove_location'),
    ]

    operations = [
        # First ensure all items have a warehouse
        migrations.RunPython(set_default_warehouse),
        
        # Then make the warehouse field non-nullable
        migrations.AlterField(
            model_name='inventoryitem',
            name='warehouse',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='inventory.warehouse'),
        ),
    ]
