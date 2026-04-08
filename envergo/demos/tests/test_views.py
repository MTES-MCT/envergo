import json
import uuid

import pytest
from django.urls import reverse

from envergo.geodata.tests.factories import (
    LineFactory,
    TerresEmergeesZoneFactory,
    herault_multipolygon,
)
from envergo.hedges.tests.factories import HedgeDataFactory

pytestmark = [pytest.mark.django_db, pytest.mark.haie]


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
    # The display geometry must be a MultiLineString. Without an explicit
    # ST_Multi wrap, ST_Collect over MultiLineString rows can yield a
    # GeometryCollection, which has `geometries` instead of `coordinates`
    # and breaks Leaflet rendering — assert the type explicitly.
    assert haies_polygon["polygon"]["type"] == "MultiLineString"
    assert len(haies_polygon["polygon"]["coordinates"]) > 0
    assert haies_polygon["legend"] == "Haies"


def test_hedges_density_around_point_demo_on_land(client):
    """Density demo with a point inside a `terres_emergees` zone.

    The default `LineFactory` setup creates no `terres_emergees` zones, so
    the on-land check returns False and the view silently exercises the
    off-land sentinel branch (density=1.0). This test seeds a real
    terres_emergees zone covering France so the on-land branch is actually
    hit, and asserts the resulting context contains real (non-sentinel)
    density values and a non-null truncated 5 km circle.
    """
    LineFactory()
    TerresEmergeesZoneFactory()
    url = reverse("demo_density")
    # WHEN I get demo page with lat/lng on land
    params = "lng=3.58123&lat=49.32252"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    # THEN the page is displayed with no error
    assert response.status_code == 200
    # AND the on-land branch is exercised: truncated 5 km circle is computed,
    # area is positive, and density is the real ratio (not the sentinel 1.0)
    assert response.context["truncated_circle_5000"] is not None
    assert response.context["area_5000_ha"] > 0
    assert response.context["density_5000"] != 1.0
    # AND the display geometry is a stable MultiLineString
    haies_polygon = json.loads(response.context["polygons"])[0]
    assert haies_polygon["polygon"]["type"] == "MultiLineString"
    assert len(haies_polygon["polygon"]["coordinates"]) > 0


def test_hedges_density_around_point_demo_off_land(client):
    """Density demo with a point outside any `terres_emergees` zone.

    Sets up a real terres_emergees zone (Hérault, in southern France) plus
    haies in northern France, then queries with a point in the north — the
    point is well outside the only land zone, so the on-land check returns
    False and the off-land sentinel branch runs. This locks in two
    contracts:

    1. Off-land density is the sentinel `1.0` and `truncated_circle` is
       `None`.
    2. The display geometry is STILL populated — clicking outside any land
       zone must not strip nearby hedges from the map. This is critical
       once the display fetch is folded into the same SQL query as the
       length aggregation: the bundle function must use the largest
       *untruncated* circle for the WHERE clause.
    """
    LineFactory()
    TerresEmergeesZoneFactory(geometry=herault_multipolygon)
    url = reverse("demo_density")
    # WHEN I get the demo page with a point in northern France (lines area),
    # which is far from the only terres_emergees zone (Hérault, in the south)
    params = "lng=3.58123&lat=49.32252"
    full_url = f"{url}?{params}"
    response = client.get(full_url)
    # THEN the page is displayed with no error
    assert response.status_code == 200
    # AND the off-land sentinel is in effect for both exposed radii
    assert response.context["truncated_circle_400"] is None
    assert response.context["truncated_circle_5000"] is None
    assert response.context["density_400"] == 1.0
    assert response.context["density_5000"] == 1.0
    assert response.context["area_400_ha"] == 0.0
    assert response.context["area_5000_ha"] == 0.0
    # AND the display geometry is still populated despite the off-land branch
    haies_polygon = json.loads(response.context["polygons"])[0]
    assert haies_polygon["polygon"]["type"] == "MultiLineString"
    assert len(haies_polygon["polygon"]["coordinates"]) > 0


def test_hedges_density_in_buffer_demo(client):
    """Test hedge density demo : inside a buffer around lines"""
    url = reverse("demo_density_project")

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


def test_hedges_density_in_buffer_demo_errors(client):
    """Test hedge density demo : inside a buffer around lines"""
    url = reverse("demo_density_project")

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
