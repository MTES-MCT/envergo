#!/bin/bash
# This script is ran by scalingo to start the application

# Interrupt the script on error
set -e

echo ">>> Starting the post_deploy hook"

python manage.py migrate

if [ "$IS_REVIEW_APP" == "True" ]
then
  python manage.py deploy_environment $APP.$REGION_NAME.scalingo.io
fi


echo ">>> Leaving the post_deploy hook"
