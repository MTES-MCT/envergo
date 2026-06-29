#!/bin/bash

echo "Starting the Celery worker ($DJANGO_SETTINGS_MODULE)"

# Time limits are a safety net behind the per-call request timeouts: even an
# un-timed-out external call can no longer wedge a worker process forever.
# soft limit lets the task raise SoftTimeLimitExceeded; hard limit kills it.
# The budget is generous because legitimate import tasks (map / species file
# processing) run for several minutes; a tighter limit would kill them and,
# combined with the global retry policy, send them into a retry loop.
celery -A config.celery_app worker --loglevel info --soft-time-limit 600 --time-limit 900
