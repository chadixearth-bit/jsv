# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0004_alter_customuser_role_alter_customuser_warehouses"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("admin", "Admin"),
                    ("manager", "Manager"),
                    ("attendant", "Attendant"),
                ],
                max_length=20,
            ),
        ),
    ]
