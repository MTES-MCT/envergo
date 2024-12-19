#!/bin/bash
# This script is ran by scalingo to start the application

echo "Starting the Publicodes node app ($DJANGO_SETTINGS_MODULE) as user `whoami`"

npm run start
