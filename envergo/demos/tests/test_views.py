import json
import uuid

import pytest
from django.test import override_settings
from django.urls import reverse

from envergo.geodata.tests.factories import LineFactory
from envergo.hedges.tests.factories import HedgeDataFactory

pytestmark = pytest.mark.django_db


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver",
    ENVERGO_AMENAGEMENT_DOMAIN="otherserver",
)
def test_hedges_density_around_point_demo(client):
    """Test hedge density demo"""
    LineFactory()
    url = reverse("demo_density")
    # WHEN I get demo page with lat/lng
    params = "lng=3.58123&lat=49.32252"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    # THEN page is displayed with no error
    assert response.status_code == 200
    # AND mtm is in context
    assert "mtm_campaign=share-demo-densite-haie" in response.context["share_btn_url"]
    # AND haies inside circle is in context
    haies_polygon = json.loads(response.context["polygons"])[0]
    assert len(haies_polygon["polygon"]["coordinates"]) > 0
    assert haies_polygon["legend"] == "Haies"


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver",
    ENVERGO_AMENAGEMENT_DOMAIN="otherserver",
)
def test_hedges_density_in_buffer_demo(client):
    """Test hedge density demo : inside a buffer around lines"""
    url = reverse("demo_density_buffer")

    # GIVEN existing haies
    hedges = HedgeDataFactory()
    # WHEN I get demo page with haies params
    params = f"haies={hedges.id}"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    # THEN page is displayed with no error
    assert response.status_code == 200
    # AND mtm is in context
    assert "&mtm_campaign=share-demo-densite-haie" in response.context["share_btn_url"]
    # AND hedge geom is in context
    assert len(response.context["hedges_to_remove_mls"]) > 0


@pytest.mark.urls("config.urls_haie")
@override_settings(
    ENVERGO_HAIE_DOMAIN="testserver",
    ENVERGO_AMENAGEMENT_DOMAIN="otherserver",
)
def test_hedges_density_in_buffer_demo_errors(client):
    """Test hedge density demo : inside a buffer around lines"""
    url = reverse("demo_density_buffer")

    # WHEN I get demo page with haies bad params
    params = "haies=1234"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    # THEN page is displayed with no error
    assert response.status_code == 200
    # AND error message is in page
    assert (
        "Ce démonstrateur fonctionne pour des haies provenant des données d'une simulation."
        in response.content.decode()
    )

    # WHEN I get demo page with not existing haies
    params = f"haies={uuid.uuid4()}"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    # THEN page is displayed with no error
    assert response.status_code == 200
    # AND error message is in page
    assert (
        "Ce démonstrateur fonctionne pour des haies provenant des données d'une simulation."
        in response.content.decode()
    )

    # WHEN I get demo page with haies no params
    full_url = f"{url}"
    response = client.get(full_url)
    # THEN page is displayed with no error
    assert response.status_code == 200
    # AND error message is in page
    assert (
        "Ce démonstrateur fonctionne pour des haies provenant des données d'une simulation."
        in response.content.decode()
    )
