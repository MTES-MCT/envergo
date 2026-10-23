import factory
from factory.django import DjangoModelFactory

from envergo.demarchenumerique.models import DemarcheConfig


class DemarcheConfigFactory(DjangoModelFactory):
    class Meta:
        model = DemarcheConfig

    demarche_numerique_number = factory.Sequence(lambda n: 10000 + n)
    pre_fill_config = [
        {
            "id": "123",
            "value": "profil",
            "mapping": {
                "autre": "Autre (collectivit\u00e9, am\u00e9nageur, gestionnaire de r\u00e9seau, particulier, etc.)",
                "agri_pac": "Exploitant-e agricole b\u00e9n\u00e9ficiaire de la PAC",
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
    display_fields = {
        "project_url": "ABC123",
    }
