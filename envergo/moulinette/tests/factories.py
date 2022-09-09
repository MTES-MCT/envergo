import factory
from factory.django import DjangoModelFactory

from envergo.geodata.tests.factories import MapFactory
from envergo.moulinette.models import Perimeter


class PerimeterFactory(DjangoModelFactory):
    class Meta:
        model = Perimeter

    name = "Loi sur l'eau Zone humide"
    map = factory.SubFactory(MapFactory)
    criterion = "envergo.moulinette.regulations.loisurleau.ZoneHumide"
