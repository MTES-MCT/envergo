#!/bin/bash
# This script is ran by scalingo to start the application

echo "Starting the Django app ($DJANGO_SETTINGS_MODULE)"

gunicorn config.wsgi:application --log-file -
