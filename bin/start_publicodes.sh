#!/bin/bash
# This script is ran by scalingo to start the application

echo "Starting the Publicodes node app ($DJANGO_SETTINGS_MODULE) as user `whoami`"
# Navigate to the publicodes directory
cd publicodes

# Install the Node.js dependencies
npm install

# add node_modules/.bin to the PATH
export PATH=$PATH:./node_modules/.bin

# Start the Node.js application
npm run serve
