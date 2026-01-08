import factory
from factory.django import DjangoModelFactory

from envergo.geodata.tests.factories import DepartmentFactory, MapFactory
from envergo.moulinette.models import (
    ConfigAmenagement,
    ConfigHaie,
    Criterion,
    MoulinetteTemplate,
    Perimeter,
    Regulation,
)


class ConfigAmenagementFactory(DjangoModelFactory):
    class Meta:
        model = ConfigAmenagement

    department = factory.SubFactory(DepartmentFactory)
    is_activated = True
    regulations_available = ["loi_sur_leau", "sage", "natura2000", "eval_env"]


class MoulinetteTemplateFactory(DjangoModelFactory):
    class Meta:
        model = MoulinetteTemplate

    config = factory.SubFactory(ConfigAmenagementFactory)
    content = factory.Faker("text")


class RegulationFactory(DjangoModelFactory):
    class Meta:
        model = Regulation

    regulation = "loi_sur_leau"
    evaluator = "envergo.moulinette.regulations.RegulationEvaluator"
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
    is_activated = True

    @factory.post_generation
    def regulations(self, create, extracted, **kwargs):
        if not create or not extracted:
            # Simple build, or nothing to add, do nothing.
            return

        # Add the iterable of groups using bulk addition
        self.regulations.add(*extracted)


class DCConfigHaieFactory(DjangoModelFactory):
    class Meta:
        model = ConfigHaie

    department = factory.SubFactory(DepartmentFactory)
    is_activated = True
    single_procedure = False
    regulations_available = [
        "conditionnalite_pac",
        "ep",
        "natura2000_haie",
        "alignement_arbres",
        "reserves_naturelles",
        "code_rural_haie",
        "regime_unique_haie",
        "sites_proteges_haie",
    ]
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


class RUConfigHaieFactory(DCConfigHaieFactory):
    single_procedure = True
    single_procedure_settings = {
        "coeff_compensation": {
            "mixte": 1.5,
            "degradee": 1.5,
            "arbustive": 1.5,
            "buissonnante": 1.5,
        }
    }
