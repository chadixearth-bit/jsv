from django.db import migrations

def add_permissions(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    
    # Get the content type for the Requisition model
    requisition_content_type, _ = ContentType.objects.get_or_create(
        app_label='requisition',
        model='requisition'
    )
    
    # Define the permissions we want to create
    permissions = [
        ('change_requisition', 'Can change requisition'),
        ('delete_requisition', 'Can delete requisition'),
        ('view_requisition', 'Can view requisition'),
        ('approve_requisition', 'Can approve requisition'),
    ]
    
    # Create the permissions
    for codename, name in permissions:
        Permission.objects.get_or_create(
            codename=codename,
            name=name,
            content_type=requisition_content_type,
        )

class Migration(migrations.Migration):
    dependencies = [
        ('requisition', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_permissions),
    ]
