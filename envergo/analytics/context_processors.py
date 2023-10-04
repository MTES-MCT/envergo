from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from config.settings.base import VISITOR_COOKIE_NAME
from envergo.analytics.models import Event


def build_usage_facet(usage_data):
    now = timezone.now()
    usage_delta = (now - usage_data["latest_date"]).days

    if usage_data["count"] >= 2:
        usage_nb = "n2"
    elif usage_data["count"] == 1:
        usage_nb = "n1"
    else:
        usage_nb = "n0"

    if usage_delta <= 60:
        usage_last = "d0"
    else:
        usage_last = "d1"

    usage_facet = f"{usage_nb}_{usage_last}"
    return usage_facet


def build_simulation_facet(simulation_data):
    now = timezone.now()
    simulation_delta = (now - simulation_data["latest_date"]).days

    if simulation_data["count"] >= 10:
        simulation_nb = "n3"
    elif simulation_data["count"] >= 2:
        simulation_nb = "n2"
    elif simulation_data["count"] == 1:
        simulation_nb = "n1"
    else:
        simulation_nb = "n0"

    if simulation_delta <= 60:
        simulation_last = "d0"
    else:
        simulation_last = "d1"

    simulation_facet = f"{simulation_nb}_{simulation_last}"
    return simulation_facet


def analytics(request):
    """Add some usage analytics to the templates context.

    We want to segment our Matomo analytics with different kind of users.

    We use matomo custom dimensions, but instead of storing raw data, it
    was decided that we manually build the facets here."""

    visitor_id = request.COOKIES[VISITOR_COOKIE_NAME]

    q_request = Q(category="evaluation") & Q(event="request")
    q_simulation = Q(category="simulateur") & Q(event="soumission")
    events = (
        Event.objects.filter(session_key=visitor_id)
        .filter(q_request | q_simulation)
        .values("category", "event")
        .annotate(count=Count("*"), latest_date=Max("date_created"))
        .order_by("event")
    )

    usage_facet = build_usage_facet(events[0])
    simulation_facet = build_simulation_facet(events[1])
    matomo_dimensions = [
        (settings.MATOMO_USAGE_DIMENSION_ID, usage_facet),
        (settings.MATOMO_SIMULATION_DIMENSION_ID, simulation_facet),
    ]

    return {
        "matomo_dimensions": matomo_dimensions,
    }
