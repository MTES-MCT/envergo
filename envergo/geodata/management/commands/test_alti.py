from queue import Queue

import requests
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from pyproj import Transformer

DIRECTIONS = [
    None,
    (0, 0),
    (0, -1),
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
]

MAX_SURFACE = 10000

WGS84_SRID = 4326
LAMBERT93_SRID = 2154
wgs_lambert_transformer = Transformer.from_crs(WGS84_SRID, LAMBERT93_SRID)
lambert_wgs_transformer = Transformer.from_crs(LAMBERT93_SRID, WGS84_SRID)


def wgs_to_lambert(longitude, latitude):
    # Gotcha!
    # In the wgs84 crs, the latitude (north, so y) axis comes first
    x, y = wgs_lambert_transformer.transform(latitude, longitude)
    return x, y


def lambert_to_wgs(x, y):
    latitude, longitude = lambert_wgs_transformer.transform(x, y)
    return longitude, latitude


class Alti:
    """Data wrapper for getting coordinates altitude."""

    def __init__(self):
        pass

    def get(self, x_y):
        lon, lat = lambert_to_wgs(*x_y)
        url = f"https://wxs.ign.fr/essentiels/alti/rest/elevation.json?lon={lon}&lat={lat}&indent=true"
        res = requests.get(url)
        data = res.json()
        alti = data["elevations"][0]["z"]
        print(f"Fetching alti to {lat},{lon} -> {alti}")
        return alti


class Mnt:
    """Stores and gives access to some terrain properties.

    Mnt = Modèle Numérique de Terrain.

    The terrain is represented as a grid with relative coordinates,
    centered on a single point.

    E.g, you can initialize a mnt centered on your house with a step of 10m.
    Then, the coordinates (0, 0) represent your house, (0, 1) is 10m south of
    you house, (-100, 0) is 1km east, etc.

    We use lambert93 coordinates because it makes coordinates computation easy.
    To move 10m east, just add 10 to the x value.
    """

    def __init__(self, x, y, step_size):
        """Initialize the MNT."""

        self.center = Point(x, y, srid=LAMBERT93_SRID)
        self.step_size = step_size
        self.attributes = {"alti": Alti()}

    @property
    def cell_area(self):
        return self.step_size ** 2

    def coords(self, cell):
        x, y = cell
        return self.center.x + x, self.center.y + y

    def compute_runoff_surface(self, max_surface):
        """Find the total surface of the water runoof interception area.

        This is a very classic Breadth-first search algorithm.

        See https://www.redblobgames.com/pathfinding/a-star/introduction.html#breadth-first-search"""

        start = (0, 0)
        frontier = Queue()
        frontier.put(start)
        reached = set()
        reached.add(start)
        reached_surface = 0

        while not frontier.empty() and reached_surface < max_surface:
            current = frontier.get()
            for next in self.neighbours(current):
                if next not in reached and self.is_flowing(next, current):
                    frontier.put(next)
                    reached.add(next)
                    reached_surface += self.cell_area

        return reached_surface

    def neighbours(self, cell):
        x, y = cell
        for i in range(-1, 2):
            for j in range(-1, 2):
                if (i, j) != (0, 0):
                    yield (x + i, y + j)

    def is_flowing(self, from_cell, to_cell):
        return self.lowest_alti_around(from_cell) == self.alti(to_cell)

    def lowest_alti_around(self, cell):
        altis = [self.alti(n) for n in self.neighbours(cell)]
        return min(altis)

    def alti(self, cell):
        return self.attributes["alti"].get(self.coords(cell))


class Command(BaseCommand):
    """Calcule la surface dont l'eau ruisselle jusqu'à un point."""

    def add_arguments(self, parser):
        parser.add_argument("x", nargs=1, type=float)
        parser.add_argument("y", nargs=1, type=float)

    def handle(self, *args, **options):

        x = options["x"][0]
        y = options["y"][0]
        mnt = Mnt(x, y, step_size=10)
        surface = mnt.compute_runoff_surface(MAX_SURFACE)

        self.stdout.write(f"Surface de ruissellement = {surface}m²")
