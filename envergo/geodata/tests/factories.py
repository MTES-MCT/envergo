import random

import factory
from django.contrib.gis.geos import MultiPolygon, Polygon
from factory import Faker as factory_Faker
from factory import fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from envergo.geodata.models import Department, Map, Zone

# This is a rough pentagon that I manually drew on geoportail and that contains
# France's mainland.
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

# Very rough department outlines
loire_atlantique_polygon = Polygon(
    [
        (-2.318813217788111, 47.11172939002415),
        (-1.8093222509912361, 46.85878309487171),
        (-1.0224264990381111, 47.06497777827326),
        (-1.336910141616236, 47.267582403961455),
        (-0.8782309423974862, 47.364409358656644),
        (-1.272365463881861, 47.826525823757436),
        (-2.679988754897486, 47.46013043348137),
        (-2.550899399428736, 47.13508980827845),
        (-2.215816391616236, 47.213505682461204),
        (-2.318813217788111, 47.11172939002415),
    ]
)

herault_polygon = Polygon(
    [
        (3.215640301549349, 43.22794194612112),
        (2.5426723773152715, 43.395887014114464),
        (3.2656957338328425, 43.913967044500254),
        (3.841333590843401, 43.96202635483297),
        (4.262633800688122, 43.58351502379401),
        (3.215640301549349, 43.22794194612112),
    ]
)

france_multipolygon = MultiPolygon([france_polygon])
loire_atlantique_multipolygon = MultiPolygon([loire_atlantique_polygon])
herault_multipolygon = MultiPolygon([herault_polygon])


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
    map_type = ""
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

    map = factory.SubFactory(MapFactory, zones=[])
    geometry = france_multipolygon


class DepartmentFactory(DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ["department"]

    department = 44
    geometry = loire_atlantique_multipolygon


class Department34Factory(DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ["department"]

    department = 34
    geometry = herault_multipolygon
