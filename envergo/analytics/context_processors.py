from django.conf import settings
from django.db.models import Count, Max, Q
from django.utils import timezone

from config.settings.base import VISITOR_COOKIE_NAME
from envergo.analytics.models import Event


def build_evalreq_facet(evalreq_data):
    now = timezone.now()
    evalreq_delta = (now - evalreq_data["latest_date"]).days

    if evalreq_data["count"] >= 2:
        evalreq_nb = "n2"
    elif evalreq_data["count"] == 1:
        evalreq_nb = "n1"
    else:
        evalreq_nb = "n0"

    if evalreq_delta <= 60:
        evalreq_last = "d0"
    else:
        evalreq_last = "d1"

    evalreq_facet = f"{evalreq_nb}_{evalreq_last}"
    return evalreq_facet


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

    visitor_id = request.COOKIES.get(VISITOR_COOKIE_NAME, None)
    if not visitor_id:
        return {}

    q_request = Q(category="evaluation") & Q(event="request")
    q_simulation = Q(category="simulateur") & Q(event="soumission")
    events = (
        Event.objects.filter(session_key=visitor_id)
        .filter(q_request | q_simulation)
        .values("category", "event")
        .annotate(count=Count("*"), latest_date=Max("date_created"))
        .order_by("event")
    )
    matomo_dimensions = []

    evalreq_data = next(
        (event for event in events if event["event"] == "request"), None
    )
    evalreq_facet = build_evalreq_facet(evalreq_data) if evalreq_data else "n0_d0"
    if evalreq_facet:
        matomo_dimensions.append(
            (settings.MATOMO_EVALREQ_DIMENSION_ID, evalreq_facet),
        )

    simulation_data = next(
        (event for event in events if event["event"] == "soumission"), None
    )
    simulation_facet = (
        build_simulation_facet(simulation_data) if simulation_data else "n0_d0"
    )
    if simulation_facet:
        matomo_dimensions.append(
            (settings.MATOMO_SIMULATION_DIMENSION_ID, simulation_facet),
        )

    return {
        "matomo_dimensions": matomo_dimensions,
    }
