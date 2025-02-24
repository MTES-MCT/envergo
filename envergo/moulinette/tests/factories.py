import factory
from factory.django import DjangoModelFactory

from envergo.geodata.tests.factories import DepartmentFactory, MapFactory
from envergo.moulinette.models import (
    ConfigAmenagement,
    ConfigHaie,
    Criterion,
    Perimeter,
    Regulation,
)


class ConfigAmenagementFactory(DjangoModelFactory):
    class Meta:
        model = ConfigAmenagement

    department = factory.SubFactory(DepartmentFactory)
    is_activated = True
    regulations_available = ["loi_sur_leau", "sage", "natura2000", "eval_env"]


class RegulationFactory(DjangoModelFactory):
    class Meta:
        model = Regulation

    regulation = "loi_sur_leau"
    has_perimeters = False


class CriterionFactory(DjangoModelFactory):
    class Meta:
        model = Criterion

    title = "Zone humide"
    regulation = factory.SubFactory(RegulationFactory)
    activation_map = factory.SubFactory(MapFactory)
    evaluator = "envergo.moulinette.regulations.loisurleau.ZoneHumide"


class PerimeterFactory(DjangoModelFactory):
    class Meta:
        model = Perimeter

    name = "Loi sur l'eau Zone humide"
    activation_map = factory.SubFactory(MapFactory)
    regulation = factory.SubFactory(RegulationFactory)
    is_activated = True


class ConfigHaieFactory(DjangoModelFactory):
    class Meta:
        model = ConfigHaie

    department = factory.SubFactory(DepartmentFactory)
    is_activated = True
    demarche_simplifiee_number = 123456
    demarche_simplifiee_pre_fill_config = [
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
    demarches_simplifiees_project_url_id = "ABC123"
