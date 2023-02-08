import pytest

from envergo.confs.models import TopBar

pytestmark = pytest.mark.django_db


def test_topbar_message_parsing():
    """Message is parsed to HTML and not enclosed in <p> tags."""

    topbar = TopBar(message_md="Hello *world*!")
    topbar.save()
    assert topbar.message_html == "Hello <em>world</em>!"
