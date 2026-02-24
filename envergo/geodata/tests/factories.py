import random

import factory
from django.contrib.gis.geos import LineString, MultiLineString, MultiPolygon, Polygon
from factory import Faker as factory_Faker
from factory import fuzzy
from factory.django import DjangoModelFactory
from faker import Faker

from envergo.geodata.models import MAP_TYPES, Department, Line, Map, Zone

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

aisne_polygon = Polygon(
    [
        (3.1718682186441027, 50.00041883371105),
        (4.2503606431506125, 49.92911270317336),
        (4.079464816057314, 49.350343310805215),
        (3.640677706563422, 49.26753056631054),
        (3.4259028609826716, 48.84681813579178),
        (2.976160950713585, 49.320267970519126),
        (3.1718682186441027, 50.00041883371105),
    ]
)

calvados_polygon = Polygon(
    [
        (-1.0763679690626593, 49.366695527098784),
        (0.2990843940771724, 49.41824158929208),
        (0.44224494627577665, 48.945376807525776),
        (-1.1172909475059614, 48.76801610637284),
        (-0.876659539266743, 49.09319617523499),
        (-1.0763679690626593, 49.366695527098784),
    ]
)

acy_polygon = Polygon(
    [
        (3.415440158691405, 49.369194107413875),
        (3.386000232543945, 49.338667914674176),
        (3.4286580847167962, 49.31931367054088),
        (3.4495149420166005, 49.35521926418238),
        (3.415440158691405, 49.369194107413875),
    ]
)

limé_polygon = Polygon(
    [
        (3.549842492004394, 49.33552931554917),
        (3.5300156029663086, 49.3152226495269),
        (3.5619017037353515, 49.31217312946501),
        (3.584561005493163, 49.32162882442222),
        (3.5807415398559566, 49.329488538022105),
        (3.5576530846557617, 49.33754274332614),
        (3.549842492004394, 49.33552931554917),
    ]
)


france_multipolygon = MultiPolygon([france_polygon])
loire_atlantique_multipolygon = MultiPolygon([loire_atlantique_polygon])
herault_multipolygon = MultiPolygon([herault_polygon])

lines = LineString(
    [
        (3.549842492004394, 49.33552931554917),
        (3.5300156029663086, 49.3152226495269),
        (3.5619017037353515, 49.31217312946501),
        (3.584561005493163, 49.32162882442222),
        (3.5807415398559566, 49.329488538022105),
        (3.5576530846557617, 49.33754274332614),
    ]
)
map_lines = MultiLineString([lines])


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

    name = factory_Faker("name")
    map_type = ""
    description = "Lorem ipsum"
    zones = factory.RelatedFactoryList(
        "envergo.geodata.tests.factories.ZoneFactory",
        factory_related_name="map",
        size=1,
    )


class LineFactory(DjangoModelFactory):
    class Meta:
        model = Line

    map = factory.SubFactory(MapFactory, map_type=MAP_TYPES.haies)
    geometry = map_lines


class ZoneFactory(DjangoModelFactory):
    class Meta:
        model = Zone

    map = factory.SubFactory(MapFactory)
    geometry = france_multipolygon
    species_taxrefs = []


class DepartmentFactory(DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ["department"]

    department = "44"
    geometry = loire_atlantique_multipolygon


class Department34Factory(DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ["department"]

    department = "34"
    geometry = herault_multipolygon
