#!/usr/bin/env bash
# exit on error
set -o errexit

cd tailwind_django
pip install --upgrade pip
pip install -r ../requirements.txt
# Explicitly install PDF-related dependencies
pip install xhtml2pdf==0.2.13 html5lib==1.1 PyPDF2==3.0.0 arabic-reshaper==3.0.0 python-bidi==0.4.2
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py create_default_superuser
