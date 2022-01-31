import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify(msg):
    """Send a simple message in a mattermost channel.

    Which channel is entirely defined in the endpoint settings.
    """
    logger.warning("[mattermost] in notify")
    endpoint = settings.MATTERMOST_ENDPOINT
    logger.warning(f"[mattermost] {endpoint}")
    if endpoint:
        payload = {"text": msg}
        res = requests.post(endpoint, json=payload)
        logger.warning(res)
        logger.warning(res.text)
    else:
        logger.warning("No mattermost endpoint configured. Doing nothing.")
