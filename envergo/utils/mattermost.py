import logging
from typing import Literal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify(msg, site: Literal["haie", "amenagement"]):
    """Send a simple message in a mattermost channel.

    Which channel is entirely defined in the endpoint settings.
    """
    endpoint = (
        settings.MATTERMOST_ENDPOINT_HAIE
        if site == "haie"
        else settings.MATTERMOST_ENDPOINT_AMENAGEMENT
    )
    if endpoint:
        payload = {"text": msg}
        r = requests.post(endpoint, json=payload)

        # Make sure we get an error if the notification failed
        r.raise_for_status()
    else:
        logger.warning(
            f"No mattermost endpoint configured. Doing nothing. Message: {msg}"
        )
