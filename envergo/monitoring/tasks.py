import logging

import requests
from django.conf import settings

from config.celery_app import app

logger = logging.getLogger(__name__)


@app.task(max_retries=0)
def send_pulse():
    if settings.HEALTH_CHECK_PULSE_URL:
        requests.head(settings.HEALTH_CHECK_PULSE_URL)
