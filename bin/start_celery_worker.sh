#!/bin/bash

echo "Starting the Celery worker ($DJANGO_SETTINGS_MODULE)"

celery -A envergo.celery worker --loglevel info
