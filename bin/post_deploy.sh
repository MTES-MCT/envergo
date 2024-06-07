#!/bin/bash
# This script is ran by scalingo to start the application

# Interrupt the script on error
set -e

echo ">>> Starting the post_deploy hook"

python manage.py migrate

# WIP to remove
echo $APP
echo $PORT
echo $CONTAINER
echo $CONTAINER_VERSION
echo $CONTAINER_SIZE
echo $CONTAINER_MEMORY
echo $HOSTNAME
echo $STACK
echo $REGION_NAME

python manage.py deploy_environment $APP

echo ">>> Leaving the post_deploy hook"
