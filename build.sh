#!/usr/bin/env bash
# exit on error
set -o errexit

cd tailwind_django
pip install --upgrade pip
pip install -r ../requirements.txt
pip install xhtml2pdf==0.2.13  # Explicitly install xhtml2pdf
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py create_default_superuser
