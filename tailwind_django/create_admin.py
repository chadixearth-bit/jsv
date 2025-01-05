import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tailwind_django.settings')
django.setup()

from django.contrib.auth.models import User
from account.models import CustomUser

# Create superuser
username = 'admin'
email = 'admin@example.com'
password = 'admin123'

try:
    # Create the superuser
    superuser = User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created successfully")

    # Create associated CustomUser
    custom_user = CustomUser.objects.create(
        user=superuser,
        role='admin'
    )
    print(f"CustomUser for '{username}' created successfully with role 'admin'")

except Exception as e:
    print(f"An error occurred: {str(e)}")
