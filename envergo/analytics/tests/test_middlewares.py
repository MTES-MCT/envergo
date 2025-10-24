import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def autouse_site(site):
    pass


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


def test_no_analytics_values(client):
    res = client.get("/", follow=True)
    assert res.status_code == 200
    assert len(res.redirect_chain) == 0

    session = client.session
    assert "mtm_campaign" not in session
    assert "mtm_source" not in session
    assert "mtm_medium" not in session
    assert "mtm_kwd" not in session


def test_analytics_values_storage(client):
    res = client.get("/?mtm_campaign=campaign&mtm_source=source", follow=True)
    assert res.status_code == 200

    # Values are stored in session
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


def test_analytics_values_url_parameters_cleanup(client):
    res = client.get(
        "/?mtm_campaign=campaign&mtm_source=source",
        follow=True,
        HTTP_REFERER="http://testserver/",
    )
    assert res.status_code == 200

    # Analytics parameters are remove from the url
    assert len(res.redirect_chain) == 1
    assert res.redirect_chain[0][0] == "/?"

    # All analytics parameters are remove from the url
    res = client.get(
        "/?mtm_campaign=campaign2&mtm_medium=medium&mtm_kwd=kwd",
        follow=True,
        HTTP_REFERER="http://testserver/",
    )
    assert len(res.redirect_chain) == 1
    assert res.redirect_chain[0][0] == "/?"

    # Only manually selected mtm parameters are cleaned
    res = client.get(
        "/?mtm_campaign=test&mtm_toto=toto&test1=test1",
        follow=True,
        HTTP_REFERER="http://testserver/",
    )
    assert len(res.redirect_chain) == 1
    assert res.redirect_chain[0][0] == "/?mtm_toto=toto&test1=test1"


def test_analytics_from_outside_are_not_cleaned(client):

    # Visit from outside link, no url cleanup
    res = client.get(
        "/?mtm_campaign=campaign&mtm_source=source",
        HTTP_REFERER="http://example.com/",
    )
    assert res.status_code == 200

    # No referer is set, this is an outside link too
    res = client.get("/?mtm_campaign=campaign&mtm_source=source")
    assert res.status_code == 200


def test_analytics_empty_values(client):
    res = client.get("/?mtm_campaign=", follow=True, HTTP_REFERER="http://testserver/")
    assert res.status_code == 200

    # Analytics parameters are remove from the url
    assert len(res.redirect_chain) == 1
    assert res.redirect_chain[0][0] == "/?"


def test_analytics_with_post_request(client):
    # We don't prevent POST queries with mtm_ parameters
    res = client.post(
        "/simulateur/formulaire/?mtm_campaign=test", HTTP_REFERER="http://testserver/"
    )
    assert res.status_code == 200
