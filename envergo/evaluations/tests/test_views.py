import pytest
from django.urls import reverse

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
    assert "Votre évaluation Loi sur l'eau est disponible !" in content


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
