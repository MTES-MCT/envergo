import json
from copy import copy
from pathlib import Path

import factory
from django.conf import settings
from factory.django import DjangoModelFactory

from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.petitions.models import DOSSIER_STATES, InvitationToken, PetitionProject
from envergo.users.tests.factories import UserFactory

DEMARCHES_SIMPLIFIEES_FAKE = {
    "ENABLED": True,
    "DOSSIER_BASE_URL": "https://www.demarches-simplifiees.example.com/",
    "PRE_FILL_API_URL": "https://www.demarches-simplifiees.example.com/api/public/v1/",
    "GRAPHQL_API_URL": "https://www.demarches-simplifiees.example.com/api/v2/graphql",
    "GRAPHQL_API_BEARER_TOKEN": None,
    "DOSSIER_DOMAIN_BLACK_LIST": [],
}

DEMARCHES_SIMPLIFIEES_FAKE_DISABLED = copy(DEMARCHES_SIMPLIFIEES_FAKE)
DEMARCHES_SIMPLIFIEES_FAKE_DISABLED["ENABLED"] = False

with open(
    Path(
        settings.APPS_DIR
        / "petitions"
        / "demarches_simplifiees"
        / "data"
        / "fake_dossier.json"
    ),
    "r",
) as file:
    GET_DOSSIER_FAKE_RESPONSE = json.load(file)


class PetitionProjectFactory(DjangoModelFactory):
    class Meta:
        model = PetitionProject

    reference = "ABC123"
    moulinette_url = (
        "http://haie.local:3000/simulateur/resultat/?profil=autre&motif=autre&reimplantation=non"
        "&haies=4406e311-d379-488f-b80e-68999a142c9d&department=44&travaux=destruction&element=haie"
    )
    hedge_data = factory.SubFactory(HedgeDataFactory)
    demarches_simplifiees_dossier_number = 21059675
    demarches_simplifiees_state = DOSSIER_STATES.draft


class PetitionProject34Factory(DjangoModelFactory):
    class Meta:
        model = PetitionProject

    reference = "ABC124"
    moulinette_url = (
        "http://haie.local:3000/simulateur/resultat/?profil=autre&motif=autre&reimplantation=non"
        "&haies=4406e311-d379-488f-b80e-68999a142c9d&department=34&travaux=destruction&element=haie"
    )
    hedge_data = factory.SubFactory(HedgeDataFactory)
    demarches_simplifiees_dossier_number = 21059676
    demarches_simplifiees_state = DOSSIER_STATES.draft


class InvitationTokenFactory(DjangoModelFactory):
    class Meta:
        model = InvitationToken

    created_by = factory.SubFactory(UserFactory)
    petition_project = factory.SubFactory(PetitionProjectFactory)
