import pytest
from django.urls import reverse

from envergo.analytics.middleware import SetVisitorIdCookie

pytestmark = pytest.mark.django_db


def test_set_visitor_id_cookie_middleware(client):
    """A single page view sets the unique visitor cookie."""

    res = client.get("/")
    request = res.wsgi_request

    assert "visitorid" in request.COOKIES
    assert request.COOKIES["visitorid"]


def test_visitor_cookie_deactivation(client):

    # Set initial cookie
    res = client.get("/")

    disable_url = reverse("disable_visitor_cookie")
    res = client.post(disable_url, data={}, follow=True)
    request = res.wsgi_request

    assert "visitorid" in request.COOKIES
    assert request.COOKIES["visitorid"] == ""

    # New page views leave the cookie unset
    res = client.get("/")
    request = res.wsgi_request
    assert "visitorid" in request.COOKIES
    assert request.COOKIES["visitorid"] == ""
