from unittest.mock import patch

import pytest

from envergo.tchap.tasks import notify

pytestmark = pytest.mark.django_db


def test_notify_queues_the_delivery():
    """notify() hands the message to Celery instead of delivering inline."""
    with patch("envergo.tchap.tasks.send_notification.delay") as mock_delay:
        notify("hello", "amenagement")

    mock_delay.assert_called_once_with("hello", "amenagement")


def test_notify_falls_back_to_mattermost_when_the_broker_refuses():
    """A broker outage costs the Tchap copy, not the whole alert."""
    with (
        patch(
            "envergo.tchap.tasks.send_notification.delay",
            side_effect=Exception("broker down"),
        ),
        patch("envergo.utils.mattermost.notify") as mock_mattermost,
    ):
        notify("hello", "amenagement")  # must not raise

    mock_mattermost.assert_called_once_with("hello", "amenagement")


def test_task_delivers_through_the_notifications_module():
    with patch("envergo.tchap.notifications.deliver") as mock_deliver:
        notify("hello", "haie")  # CELERY_TASK_ALWAYS_EAGER runs it inline

    mock_deliver.assert_called_once_with("hello", "haie")
