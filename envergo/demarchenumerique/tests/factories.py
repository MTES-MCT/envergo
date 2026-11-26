from copy import deepcopy

import factory
from factory.django import DjangoModelFactory

from envergo.demarchenumerique.models import DemarcheConfig

PRE_FILL_CONFIG = [
    {
        "id": "123",
        "value": "profil",
        "mapping": {
            "autre": "Autre (collectivité, aménageur, gestionnaire de réseau, particulier, etc.)",
            "agri_pac": "Exploitant-e agricole bénéficiaire de la PAC",
        },
    },
    {
        "id": "456",
        "value": "conditionnalite_pac.result",
        "mapping": {"soumis": True, "non_soumis": False},
    },
    {"id": "789", "value": "url_projet"},
    {"id": "321", "value": "ref_projet"},
    {"id": "654", "value": "url_moulinette"},
]

DISPLAY_FIELDS = {
    "project_url": "ABC123",
}


class DemarcheConfigFactory(DjangoModelFactory):
    class Meta:
        model = DemarcheConfig

    demarche_numerique_number = factory.Sequence(lambda n: 10000 + n)
    # Each config gets its own copy, so a test editing one in place leaks into no other test.
    pre_fill_config = factory.LazyFunction(lambda: deepcopy(PRE_FILL_CONFIG))
    display_fields = factory.LazyFunction(lambda: deepcopy(DISPLAY_FIELDS))
