import random
from string import ascii_uppercase

import factory
from django.contrib.gis.geos import MultiPolygon, Polygon
from factory import Faker as factory_Faker
from factory import fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from envergo.geodata.models import Department, Map, Parcel, Zone


def generate_section():
    length = random.randint(1, 2)
    section = "".join(random.choices(ascii_uppercase, k=length))
    return section


# Shamelessly stolen frow SO
# https://stackoverflow.com/a/53570031/665797


class FuzzyPolygon(factory.fuzzy.BaseFuzzyAttribute):
    """Yields random polygon"""

    def __init__(self, length=None, **kwargs):
        if length is None:
            length = random.randint(3, 20)
        if length < 3:
            raise Exception("Polygon needs to be 3 or greater in length.")
        self.length = length
        super().__init__(**kwargs)

    def get_random_coords(self):
        faker = Faker()
        return (
            faker.latitude(),
            faker.longitude(),
        )

    def fuzz(self):
        prefix = suffix = self.get_random_coords()
        coords = [self.get_random_coords() for __ in range(self.length - 1)]
        return Polygon([prefix] + coords + [suffix])


class FuzzyMultiPolygon(factory.fuzzy.BaseFuzzyAttribute):
    """Yields random multipolygon"""

    def __init__(self, length=None, **kwargs):
        if length is None:
            length = random.randint(2, 20)
        if length < 2:
            raise Exception("MultiPolygon needs to be 2 or greater in length.")
        self.length = length
        super().__init__(**kwargs)

    def fuzz(self):
        polygons = [FuzzyPolygon().fuzz() for __ in range(self.length)]
        return MultiPolygon(*polygons)


class ParcelFactory(DjangoModelFactory):
    class Meta:
        model = Parcel

    commune = fuzzy.FuzzyInteger(10000, 90000)
    section = factory.LazyFunction(generate_section)
    prefix = "000"
    order = fuzzy.FuzzyInteger(1, 9999)


class MapFactory(DjangoModelFactory):
    class Meta:
        model = Map

    name = factory_Faker("name")
    # file = Faker("file", locale="fr")
    data_type = "zone_humide"
    description = "Lorem ipsum"


class ZoneFactory(DjangoModelFactory):
    class Meta:
        model = Zone

    map = factory.SubFactory(MapFactory)
    geometry = FuzzyMultiPolygon()


class DepartmentFactory(DjangoModelFactory):
    class Meta:
        model = Department

    department = 61  # Orne
    geometry = FuzzyMultiPolygon()
