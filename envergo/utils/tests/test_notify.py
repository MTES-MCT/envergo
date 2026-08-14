from unittest.mock import patch

from envergo.utils import mattermost, tchap


def test_tchap_notify_calls_mattermost_as_backup(settings):
    """tchap.notify() must always relay to Mattermost, even while Tchap isn't
    configured yet (today's state) — this is the primary/backup contract.
    """
    settings.TCHAP_ACCESS_TOKEN = None

    with patch("envergo.utils.mattermost.notify") as mock_mattermost_notify:
        tchap.notify("hello", "amenagement")

    mock_mattermost_notify.assert_called_once_with("hello", "amenagement")


def test_tchap_notify_calls_mattermost_even_if_tchap_send_fails(settings):
    """A Tchap-side failure must not prevent the Mattermost backup send."""
    settings.TCHAP_ACCESS_TOKEN = "fake-token"
    settings.TCHAP_ROOM_ID_AMENAGEMENT = "!fakeroom:example.org"

    with (
        patch("envergo.utils.tchap._notify_with_lock", side_effect=Exception("boom")),
        patch("envergo.utils.mattermost.notify") as mock_mattermost_notify,
    ):
        tchap.notify("hello", "amenagement")

    mock_mattermost_notify.assert_called_once_with("hello", "amenagement")


def test_mattermost_notify_does_not_call_tchap():
    """Tchap is the primary channel and calls Mattermost, not the other way
    around: mattermost.notify() must only ever talk to Mattermost.
    """
    with patch("envergo.utils.tchap.notify") as mock_tchap_notify:
        mattermost.notify("hello", "amenagement")

    mock_tchap_notify.assert_not_called()
