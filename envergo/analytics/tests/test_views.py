
from unittest.mock import patch

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


@patch('envergo.utils.mattermost.notify')
@patch('envergo.geodata.utils.get_data_from_coords')
def test_feedback_sent(mock_notify, _mock_api, client):

    feedback_url = reverse('feedback_submit')
    referer_url = "https://envergo/simulateur/resultat/?created_surface=42&existing_surface=42&lng=-1.77498&lat=47.21452&is_lotissement=oui"  # noqa
    data = {
        'feedback': 'Oui',
        'message': "Ceci n'est pas un message",
        'you_are': 'porteur',
    }
    res = client.post(feedback_url, data=data, HTTP_REFERER=referer_url)
    assert res.status_code == 302
    assert referer_url in res.url
    assert '&feedback=true' in res.url
    mock_notify.assert_called_once()
