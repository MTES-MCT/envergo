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
