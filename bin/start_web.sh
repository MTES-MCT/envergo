#!/bin/bash
# This script is ran by scalingo to start the application

echo "Starting the Django app ($DJANGO_SETTINGS_MODULE) as user `whoami`"

gunicorn config.wsgi:application --preload --workers=9 --max-requests 300 --max-requests-jitter 50 --log-file -
