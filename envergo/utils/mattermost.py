import requests
from django.conf import settings


def notify(msg):
    """Send a simple message in a mattermost channel.

    Which channel is entirely defined in the endpoint settings.
    """
    endpoint = settings.MATTERMOST_ENDPOINT
    if endpoint:
        payload = {"text": msg}
        requests.post(endpoint, json=payload)
    else:
        print(msg)
