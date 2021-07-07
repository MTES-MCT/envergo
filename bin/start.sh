#!/bin/bash
# This script is ran by scalingo to start the application

echo "Deploying the EnvErgo Django app ($DJANGO_SETTINGS_MODULE)"
python manage.py compilemessages
python manage.py collectstatic --noinput
python manage.py compress --force
gunicorn config.wsgi:application --log-file -
