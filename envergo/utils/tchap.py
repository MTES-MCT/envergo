import logging
from typing import Literal
from urllib.parse import quote, urljoin

import requests
from django.conf import settings

from envergo.utils.markdown import markdown_to_html
from envergo.utils.urls import update_qs

logger = logging.getLogger(__name__)


def notify(msg, site: Literal["haie", "amenagement"]):
    """Send a simple message to a Tchap channel.

    Which channel is used is entirely defined by the endpoint settings."""
    room_id = (
        settings.TCHAP_ROOM_ID_HAIE
        if site == "haie"
        else settings.TCHAP_ROOM_ID_AMENAGEMENT
    )
    if (
        not room_id
        or not settings.TCHAP_HOMESERVER_URL
        or not settings.TCHAP_ACCESS_TOKEN
    ):
        logger.warning(f"No Tchap endpoint configured. Doing nothing. Message: {msg}")
        return

    room_path = f"_matrix/client/v3/rooms/{quote(room_id, safe='')}/send/m.room.message"
    endpoint = urljoin(settings.TCHAP_HOMESERVER_URL, room_path)
    endpoint = update_qs(endpoint, {"access_token": settings.TCHAP_ACCESS_TOKEN})
    payload = {
        "msgtype": "m.text",
        "body": msg,
        "format": "org.matrix.custom.html",
        "formatted_body": markdown_to_html(msg, "nl2br", "fenced_code"),
    }
    try:
        r = requests.post(endpoint, json=payload, timeout=settings.DEFAULT_HTTP_TIMEOUT)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.warning("Could not send the Tchap notification", extra={"exception": e})
