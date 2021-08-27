import pytest
from django.urls import reverse

from envergo.evaluations.models import Request

pytestmark = pytest.mark.django_db


def test_searching_inexisting_eval(client):
    """Searching an eval that does not exist returns an error message."""

    search_url = reverse("evaluation_search")
    application_number = "PC05112321D0123"
    res = client.post(
        search_url, data={"application_number": application_number}, follow=True
    )
    assert res.status_code == 404

    content = res.content.decode("utf-8")
    assert (
        "l'évaluation Loi sur l'eau n'est pas encore disponible pour ce projet"
        in content
    )


def test_search_existing_eval(client, evaluation):
    """Searching for an eval links to it."""

    search_url = reverse("evaluation_search")
    res = client.post(
        search_url,
        data={"application_number": evaluation.application_number},
        follow=True,
    )
    assert res.status_code == 200

    content = res.content.decode("utf-8")
    assert "<h1>Évaluation Loi sur l'eau</h1>" in content


def test_search_form_allows_spaces_in_application_field(client, evaluation):
    """Don't prevent spaces in the search field."""

    evaluation.application_number = "PC05112321D0123"
    evaluation.save()

    search_url = reverse("evaluation_search")
    res = client.post(
        search_url,
        data={"application_number": "pc 051 123 21 d0123"},
        follow=True,
    )
    assert res.status_code == 200


def test_eval_request_creation(client):
    data = {
        "address": "11B rue Barnier 34110 Vic la Gardiole",
        "parcel-TOTAL_FORMS": "3",
        "parcel-INITIAL_FORMS": "0",
        "parcel-MIN_NUM_FORMS": "0",
        "parcel-MAX_NUM_FORMS": "1000",
        "parcel-0-commune": "34333",
        "parcel-0-section": "BV",
        "parcel-0-prefix": "000",
        "parcel-0-order": "68",
        "application_number": "PC04412321D0123",
        "created_surface": "250",
        "existing_surface": "100",
        "contact_email": "toto@tata.com",
        "phone_number": "0612345678",
    }
    request_url = reverse("request_evaluation")
    request_qs = Request.objects.all()

    assert request_qs.count() == 0

    res = client.post(request_url, data=data)
    assert res.status_code == 302
    assert request_qs.count() == 1
