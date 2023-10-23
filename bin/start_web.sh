#!/bin/bash
# This script is ran by scalingo to start the application

echo "Starting the Django app ($DJANGO_SETTINGS_MODULE) as user `whoami`"

gunicorn config.wsgi:application --preload --max-requests 600 --log-file -
