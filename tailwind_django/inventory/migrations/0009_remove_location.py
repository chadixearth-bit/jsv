from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0008_inventoryitem_location'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='inventoryitem',
            name='location',
        ),
    ]
