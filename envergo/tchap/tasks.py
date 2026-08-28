import logging

from config.celery_app import app
from envergo.tchap import notifications
from envergo.utils import mattermost

logger = logging.getLogger(__name__)


@app.task(autoretry_for=(), max_retries=0)
def send_notification(msg, site):
    """Deliver a queued notification to Tchap, then to Mattermost.

    Opts out of the default retry policy: a Tchap exchange that got far
    enough to send would post twice on a replay. A notification is worth less
    than a duplicate, and both delivery paths already swallow their own
    failures, so a raise here means a bug rather than a flaky third party.
    """
    notifications.deliver(msg, site)


def notify(msg, site):
    """Queue `msg` for delivery to Tchap and Mattermost."""
    try:
        send_notification.delay(msg, site)
    except Exception as e:
        logger.warning("Could not queue the tchap notification", extra={"exception": e})
        mattermost.notify(msg, site)
