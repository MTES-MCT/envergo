from unittest.mock import patch

import pytest
import requests

from envergo.utils.tchap import notify

HAIE_ENDPOINT = (
    "https://tchap.example.org"
    "/_matrix/client/v3/rooms/%21haie%3Aexample.org/send/m.room.message"
    "?access_token=fake-token"
)


@pytest.fixture(autouse=True)
def tchap_settings(settings):
    """A fake but complete Tchap config, so notify() takes the sending path."""
    settings.TCHAP_HOMESERVER_URL = "https://tchap.example.org"
    settings.TCHAP_ACCESS_TOKEN = "fake-token"
    settings.TCHAP_ROOM_ID_HAIE = "!haie:example.org"
    settings.TCHAP_ROOM_ID_AMENAGEMENT = "!amenagement:example.org"


@pytest.fixture(autouse=True)
def mock_mattermost():
    """Keep the Mattermost fallback from reaching the network."""
    with patch("envergo.utils.mattermost.notify") as mock:
        yield mock


@patch("envergo.utils.tchap.requests.post")
def test_notify_posts_the_message(mock_post, settings):
    notify("hello", "haie")

    mock_post.assert_called_once()
    assert mock_post.call_args.args[0] == HAIE_ENDPOINT
    assert mock_post.call_args.kwargs["timeout"] == settings.DEFAULT_HTTP_TIMEOUT


@patch("envergo.utils.tchap.requests.post")
def test_notify_encodes_the_room_id(mock_post, settings):
    """Matrix room ids carry characters that are illegal raw in a path segment."""

    settings.TCHAP_ROOM_ID_HAIE = "!a b:example.org"
    notify("hello", "haie")

    url = mock_post.call_args.args[0]
    assert "/rooms/%21a%20b%3Aexample.org/send/" in url


@pytest.mark.parametrize(
    "homeserver_url",
    ["https://tchap.example.org", "https://tchap.example.org/"],
)
@patch("envergo.utils.tchap.requests.post")
def test_notify_ignores_the_homeserver_trailing_slash(
    mock_post, settings, homeserver_url
):
    settings.TCHAP_HOMESERVER_URL = homeserver_url
    notify("hello", "haie")

    assert mock_post.call_args.args[0] == HAIE_ENDPOINT


@pytest.mark.parametrize(
    "site, room_segment",
    [
        ("haie", "%21haie%3Aexample.org"),
        ("amenagement", "%21amenagement%3Aexample.org"),
    ],
)
@patch("envergo.utils.tchap.requests.post")
def test_notify_picks_the_room_for_the_site(mock_post, site, room_segment):
    notify("hello", site)

    assert f"/rooms/{room_segment}/send/" in mock_post.call_args.args[0]


@patch("envergo.utils.tchap.requests.post")
def test_notify_sends_markdown_as_html(mock_post):
    notify("**gras**", "haie")

    payload = mock_post.call_args.kwargs["json"]
    assert payload["msgtype"] == "m.text"
    assert payload["format"] == "org.matrix.custom.html"
    assert payload["body"] == "**gras**"
    assert "<strong>gras</strong>" in payload["formatted_body"]


@pytest.mark.parametrize(
    "missing_setting",
    ["TCHAP_ROOM_ID_HAIE", "TCHAP_HOMESERVER_URL", "TCHAP_ACCESS_TOKEN"],
)
@patch("envergo.utils.tchap.requests.post")
def test_notify_does_nothing_when_unconfigured(
    mock_post, mock_mattermost, settings, missing_setting
):
    """An incomplete config is the default one, and must stay silent."""

    setattr(settings, missing_setting, None)
    notify("hello", "haie")

    mock_post.assert_not_called()
    mock_mattermost.assert_called_once_with("hello", "haie")


@patch("envergo.utils.tchap.requests.post")
def test_notify_swallows_connection_errors(mock_post, mock_mattermost):
    """Notifications are fire-and-forget: an outage must not reach the caller."""

    mock_post.side_effect = requests.exceptions.ConnectionError("boom")
    notify("hello", "haie")

    mock_mattermost.assert_called_once_with("hello", "haie")


@patch("envergo.utils.tchap.requests.post")
def test_notify_swallows_http_errors(mock_post, mock_mattermost):
    mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "403"
    )
    notify("hello", "haie")

    mock_mattermost.assert_called_once_with("hello", "haie")


@patch("envergo.utils.tchap.requests.post")
def test_notify_always_notifies_mattermost(mock_post, mock_mattermost):
    notify("hello", "haie")

    mock_mattermost.assert_called_once_with("hello", "haie")
