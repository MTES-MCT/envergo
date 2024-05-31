import random
from string import ascii_uppercase

import factory
from django.contrib.gis.geos import MultiPolygon, Polygon
from factory import Faker as factory_Faker
from factory import fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from envergo.geodata.models import Department, Map, Zone


def generate_section():
    length = random.randint(1, 2)
    section = "".join(random.choices(ascii_uppercase, k=length))
    return section


# Shamelessly stolen frow SO
# https://stackoverflow.com/a/53570031/665797


france_polygon = Polygon(
    [
        (2.239523057461999, 51.37848260569899),
        (-5.437949095065911, 48.830042871275225),
        (-2.020973593289057, 42.22052255703733),
        (7.672371135600932, 42.3263119734425),
        (9.759728555096416, 49.41947007260785),
        (2.239523057461999, 51.37848260569899),
    ]
)
france_multipolygon = MultiPolygon([france_polygon])


class FuzzyPolygon(fuzzy.BaseFuzzyAttribute):
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


class FuzzyMultiPolygon(fuzzy.BaseFuzzyAttribute):
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


class MapFactory(DjangoModelFactory):
    class Meta:
        model = Map
        skip_postgeneration_save = True

    name = factory_Faker("name")
    map_type = "zone_humide"
    description = "Lorem ipsum"

    @factory.post_generation
    def zones(obj, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            obj.zones.add(*extracted)
        else:
            ZoneFactory(map=obj)


class ZoneFactory(DjangoModelFactory):
    class Meta:
        model = Zone

    map = factory.SubFactory(MapFactory)
    geometry = france_multipolygon


class DepartmentFactory(DjangoModelFactory):
    class Meta:
        model = Department

    department = 44
    geometry = france_multipolygon
