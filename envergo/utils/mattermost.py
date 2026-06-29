import logging
from typing import Literal

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def notify(msg, site: Literal["haie", "amenagement"]):
    """Send a simple message to a mattermost channel, best-effort.

    Which channel is used is entirely defined by the endpoint settings.

    Notifications are fire-and-forget: a failure to reach Mattermost is logged
    but never raised. notify is called from both web views and Celery tasks, so
    raising would either return a 500 to a user or pointlessly retry a whole
    business task because a non-critical notification could not be delivered.
    """
    endpoint = (
        settings.MATTERMOST_ENDPOINT_HAIE
        if site == "haie"
        else settings.MATTERMOST_ENDPOINT_AMENAGEMENT
    )
    if not endpoint:
        logger.warning(
            f"No mattermost endpoint configured. Doing nothing. Message: {msg}"
        )
        return

    payload = {"text": msg}
    try:
        r = requests.post(endpoint, json=payload, timeout=settings.DEFAULT_HTTP_TIMEOUT)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.warning(
            "Could not send the mattermost notification", extra={"exception": e}
        )
