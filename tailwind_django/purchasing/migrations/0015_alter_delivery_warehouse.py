from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0007_globalsettings_inventoryitem_description_and_more'),
        ('purchasing', '0014_populate_delivery_warehouse'),
    ]

    operations = [
        migrations.AlterField(
            model_name='delivery',
            name='warehouse',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                to='inventory.warehouse'
            ),
        ),
    ]
