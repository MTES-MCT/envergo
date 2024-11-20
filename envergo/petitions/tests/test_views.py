from unittest.mock import patch

import pytest
from django.test import RequestFactory

from envergo.moulinette.tests.factories import ConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory
from envergo.petitions.views import PetitionProjectCreate

pytestmark = pytest.mark.django_db


@patch("requests.post")
@patch("envergo.petitions.views.reverse")
def test_pre_fill_demarche_simplifiee(mock_reverse, mock_post):
    mock_reverse.return_value = "http://haie.local:3000/projet/ABC123"

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "dossier_url": "demarche_simplifiee_url",
        "state": "prefilled",
        "dossier_id": "RG9zc2llci0yMTA3NTY2NQ==",
        "dossier_number": 21075665,
        "dossier_prefill_token": "W3LFL68vStyL62kRBdJSGU1f",
    }
    ConfigHaieFactory()

    view = PetitionProjectCreate()
    factory = RequestFactory()
    request = factory.get("")
    view.request = request

    petition_project = PetitionProjectFactory()
    demarche_simplifiee_url = view.pre_fill_demarche_simplifiee(petition_project)

    assert demarche_simplifiee_url == "demarche_simplifiee_url"

    # Assert the body of the requests.post call
    expected_body = {
        "champ_123": "Autre (collectivité, aménageur, gestionnaire de réseau, "
        "particulier, etc.)",
        "champ_321": "ABC123",
        "champ_456": None,  # improve this test by configuring a result for bcae8
        "champ_654": "http://haie.local:3000/simulateur/resultat/?profil=autre&motif=autre&reimplantation=non"
        "&haies=4406e311-d379-488f-b80e-68999a142c9d&department=44&travaux=destruction&element=haie",
        "champ_789": "http://haie.local:3000/projet/ABC123",
    }
    mock_post.assert_called_once()
    assert mock_post.call_args[1]["json"] == expected_body
