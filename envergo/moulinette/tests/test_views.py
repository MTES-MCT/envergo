import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


HOME_TITLE = "Évaluez à quelles réglementations votre projet de construction est soumis"
RESULT_TITLE = "Réglementations environnementales : évaluation personnalisée"
FORM_ERROR = (
    "Nous n'avons pas pu traiter votre demande car le formulaire contient des erreurs."
)


def test_moulinette_home(client):
    url = reverse("moulinette_home")
    res = client.get(url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR not in res.content.decode()


def test_moulinette_result(client):
    url = reverse("moulinette_home")
    params = "created_surface=10000&existing_surface=10000&lng=0.75006&lat=48.49680"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert HOME_TITLE not in res.content.decode()
    assert RESULT_TITLE in res.content.decode()
    assert FORM_ERROR not in res.content.decode()


def test_moulinette_form_error(client):
    url = reverse("moulinette_home")
    params = "bad_param=true"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR in res.content.decode()


def test_moulinette_utm_param(client):
    url = reverse("moulinette_home")
    params = "utm_campaign=test"
    full_url = f"{url}?{params}"
    res = client.get(full_url)

    assert res.status_code == 200
    assert HOME_TITLE in res.content.decode()
    assert RESULT_TITLE not in res.content.decode()
    assert FORM_ERROR not in res.content.decode()
