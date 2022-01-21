import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify(msg):
    """Send a simple message in a mattermost channel.

    Which channel is entirely defined in the endpoint settings.
    """
    endpoint = settings.MATTERMOST_ENDPOINT
    logger.warning(f"Sending mattermost notification {endpoint}")
    if endpoint:
        payload = {"text": msg}
        res = requests.post(endpoint, json=payload)
        logger.warning(res)
    else:
        logger.warning("No mattermost endpoint configured. Doing nothing.")
