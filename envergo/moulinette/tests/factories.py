import factory
from factory.django import DjangoModelFactory

from envergo.geodata.tests.factories import DepartmentFactory, MapFactory
from envergo.moulinette.models import MoulinetteConfig, Perimeter


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
