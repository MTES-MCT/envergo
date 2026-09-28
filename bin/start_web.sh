#!/bin/bash
# This script is run by Scalingo to start the application.
# It starts gunicorn behind nginx, which handles:
# - proxying all requests to gunicorn
# - serving public hosted files via X-Accel-Redirect to S3

set -e

echo "Starting the Django app ($DJANGO_SETTINGS_MODULE) as user $(whoami)"

basedir="$(cd -P "$(dirname "$(dirname "$0")")" && pwd)"

# Render nginx configuration from erb templates.
erb "$basedir/base_nginx.conf.erb" > "$basedir/vendor/nginx/conf/nginx.conf"
erb "$basedir/nginx.conf.erb" > "$basedir/vendor/nginx/conf/site.conf"

# Start gunicorn in the background on a unix socket.
gunicorn config.wsgi:application \
    --bind unix:/tmp/gunicorn.sock \
    --preload \
    --workers=9 \
    --timeout 120 \
    --max-requests 300 \
    --max-requests-jitter 50 \
    --log-file - &

# Start nginx in the foreground (Scalingo expects the web process to stay alive).
nginx -p "$basedir/vendor/nginx" -c "$basedir/vendor/nginx/conf/nginx.conf"
