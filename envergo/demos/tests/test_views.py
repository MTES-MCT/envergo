import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver",
    ENVERGO_AMENAGEMENT_DOMAIN="otherserver",
)
def test_hedges_density_demo(client):
    """Test hedge density demo"""
    url = reverse("demo_density")
    params = "lng=-0.72510&lat=49.08247"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    assert response.status_code == 200
