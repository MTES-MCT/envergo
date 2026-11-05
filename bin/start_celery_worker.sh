#!/bin/bash

echo "Starting the Celery worker ($DJANGO_SETTINGS_MODULE)"

celery -A config.celery_app worker --loglevel info
