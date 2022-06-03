import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify(msg):
    """Send a simple message in a mattermost channel.

    Which channel is entirely defined in the endpoint settings.
    """
    endpoint = settings.MATTERMOST_ENDPOINT
    if endpoint:
        payload = {"text": msg}
        requests.post(endpoint, json=payload)
    else:
        logger.warning("No mattermost endpoint configured. Doing nothing.")
