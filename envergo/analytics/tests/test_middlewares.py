import pytest
from django.urls import reverse

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


def test_store_mtm_values(client):
    client.get("/")
    session = client.session
    assert "mtm_campaign" not in session
    assert "mtm_source" not in session
    assert "mtm_medium" not in session
    assert "mtm_kwd" not in session

    # mtm parameters are stored in session
    client.get("/?mtm_campaign=campaign&mtm_source=source")
    session = client.session
    assert session["mtm_campaign"] == "campaign"
    assert session["mtm_source"] == "source"
    assert "mtm_medium" not in session
    assert "mtm_kwd" not in session

    # mtm parameters can be overriden
    client.get("/?mtm_campaign=campaign2&mtm_medium=medium&mtm_kwd=kwd")
    session = client.session
    assert session["mtm_campaign"] == "campaign2"
    assert session["mtm_source"] == "source"
    assert session["mtm_medium"] == "medium"
    assert session["mtm_kwd"] == "kwd"

    # only manually selected mtm parameters are stored
    client.get("/?mtm_toto=toto")
    session = client.session
    assert "toto" not in session
