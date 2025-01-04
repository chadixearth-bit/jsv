from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('purchasing', '0016_auto_20250103_1151'),
    ]

    operations = [
        # Skip any database operations
        migrations.RunPython(migrations.RunPython.noop)
    ]
