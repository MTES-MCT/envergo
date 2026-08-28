import logging

from config.celery_app import app
from envergo.tchap import notifications
from envergo.utils import mattermost

logger = logging.getLogger(__name__)


@app.task
def send_notification(msg, site):
    """Deliver a queued notification to Tchap, then to Mattermost.

    Never raises, so the default retry policy (see
    `config.celery_app.BaseTaskWithRetry`) never replays a message: a Tchap
    exchange that got far enough to send would otherwise post twice.
    """
    notifications.deliver(msg, site)


def notify(msg, site):
    """Queue `msg` for delivery to Tchap and Mattermost."""
    try:
        send_notification.delay(msg, site)
    except Exception as e:
        logger.warning("Could not queue the tchap notification", extra={"exception": e})
        mattermost.notify(msg, site)
