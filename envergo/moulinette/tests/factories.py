import factory
from factory.django import DjangoModelFactory

from envergo.geodata.tests.factories import DepartmentFactory, MapFactory
from envergo.moulinette.models import Criterion, MoulinetteConfig, Perimeter, Regulation


class PerimeterFactory(DjangoModelFactory):
    class Meta:
        model = Perimeter

    name = "Loi sur l'eau Zone humide"
    map = factory.SubFactory(MapFactory)
    criterion = "envergo.moulinette.regulations.loisurleau.ZoneHumide"


class MoulinetteConfigFactory(DjangoModelFactory):
    class Meta:
        model = MoulinetteConfig

    department = factory.SubFactory(DepartmentFactory)
    is_activated = True


class RegulationFactory(DjangoModelFactory):
    class Meta:
        model = Regulation

    title = "Loi sur l'eau"
    slug = "loi_sur_leau"
    perimeter = factory.SubFactory(MapFactory)


class CriterionFactory(DjangoModelFactory):
    class Meta:
        model = Criterion

    title = "Zone humide"
    slug = "zone_humide"
    regulation = factory.SubFactory(RegulationFactory)
    evaluator = "envergo.moulinette.regulations.loisurleau.ZoneHumide"
    perimeter = factory.SubFactory(MapFactory)
