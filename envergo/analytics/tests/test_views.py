from unittest.mock import patch

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@patch("envergo.geodata.utils.get_data_from_coords")
@patch("envergo.analytics.views.notify")
def test_feedback_sent(mock_notify, _mock_api, client, site):

    feedback_url = reverse("feedback_submit")
    referer_url = "https://envergo/simulateur/resultat/?created_surface=42&existing_surface=42&lng=-1.77498&lat=47.21452"  # noqa
    data = {
        "useful-feedback": "Oui",
        "useful-message": "Ceci n'est pas un message",
        "useful-you_are": "porteur",
    }
    res = client.post(feedback_url, data=data, HTTP_REFERER=referer_url)
    assert res.status_code == 302
    assert referer_url in res.url
    assert "&feedback=true" in res.url
    mock_notify.assert_called_once()


@pytest.mark.parametrize("metadata", ["null", ""])
@patch("envergo.analytics.views.log_event")
def test_event_with_empty_metadata(mock_log_event, client, site, metadata):
    data = {"category": "compliance", "action": "page-click", "metadata": metadata}
    res = client.post(reverse("events"), data=data)
    assert res.json() == {"status": "ok"}
    mock_log_event.assert_called_once()
    assert mock_log_event.call_args.kwargs == {}


@pytest.mark.parametrize("metadata", ["[1, 2]", '"foo"', "42"])
@patch("envergo.analytics.views.log_event")
def test_event_with_non_object_metadata(mock_log_event, client, site, metadata):
    data = {"category": "compliance", "action": "page-click", "metadata": metadata}
    res = client.post(reverse("events"), data=data)
    assert res.json()["status"] == "error"
    mock_log_event.assert_not_called()


@patch("envergo.analytics.views.log_event")
def test_event_with_metadata(mock_log_event, client, site):
    data = {
        "category": "compliance",
        "action": "page-click",
        "metadata": '{"request_reference": "ABC123", "version": "v2"}',
    }
    res = client.post(reverse("events"), data=data)
    assert res.json() == {"status": "ok"}
    assert mock_log_event.call_args.kwargs == {
        "request_reference": "ABC123",
        "version": "v2",
    }
