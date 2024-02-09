import random
import statistics
from queue import Queue

import matplotlib.pyplot as plt
import numpy as np
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

PAGE_SIZE = 10

WGS84_SRID = 4326
LAMBERT93_SRID = 2154
wgs_lambert_transformer = Transformer.from_crs(WGS84_SRID, LAMBERT93_SRID)
lambert_wgs_transformer = Transformer.from_crs(LAMBERT93_SRID, WGS84_SRID)


def wgs_to_lambert(longitude, latitude):
    # Gotcha!
    # In the wgs84 crs, the latitude (north / y) axis comes first
    x, y = wgs_lambert_transformer.transform(latitude, longitude)
    return x, y


def lambert_to_wgs(x, y):
    latitude, longitude = lambert_wgs_transformer.transform(x, y)
    return longitude, latitude


class RgeAltiClient:
    def fetch_points(self, points):
        """Fetch altitude data for a list of points."""

        # We have a bunch of lambert93 coordinates
        # We want a list corresponding list of longitudes and latitudes, as strings
        wgs_points = [lambert_to_wgs(*p) for p in points]
        as_strings = [(str(lon), str(lat)) for lon, lat in wgs_points]
        longitudes, latitudes = zip(*as_strings)
        longitude_str = "|".join(longitudes)
        latitude_str = "|".join(latitudes)

        # Time for the api query, yeah!
        url = f"https://wxs.ign.fr/essentiels/alti/rest/elevation.json?lon={longitude_str}&lat={latitude_str}&zonly=true"  # noqa
        res = requests.get(url)
        data = res.json()
        altis = data["elevations"]
        return altis


class Alti:
    """Data wrapper for getting coordinates altitude.

    Get data efficiently by fetching blocks of values at once.
    """

    def __init__(self, step_size, page_size=PAGE_SIZE):
        self.step_size = step_size
        self.page_size = page_size
        self.value_delta = step_size * page_size
        self._pages = {}

    def get(self, cell):
        """Fetch a single value by retrieving it from the correct page."""

        cell = self.snap(cell)
        page = self.get_page_for(cell)
        x, y = self.get_data_index(cell)

        return page[x][y]

    def snap(self, cell):
        """Snap custom coordinates to the grid.

        E.g coordinates (65, 47) are rounded to (60, 50) if the step size is 10.
        """
        cell_x = round(cell[0] / self.step_size) * self.step_size
        cell_y = round(cell[1] / self.step_size) * self.step_size
        return cell_x, cell_y

    def get_page_for(self, cell):
        """Return the page containing data for the cell."""

        page_index = self.get_page_index(cell)
        if page_index not in self._pages:
            self._pages[page_index] = self.build_page(page_index)
        return self._pages[page_index]

    def get_data_index(self, cell):
        """Get the cell value coordinates inside the page."""

        x = (cell[0] // self.step_size) % self.page_size
        y = (cell[1] // self.step_size) % self.page_size
        return x, y

    def get_page_index(self, cell):
        """Returns the identifier of page containing the cell."""

        x = cell[0] // self.value_delta
        y = cell[1] // self.value_delta
        return x, y

    def build_page(self, x_y):
        """Fetch and store data for a given page."""

        x, y = x_y
        min_x, min_y = x * self.value_delta, y * self.value_delta
        max_x, max_y = min_x + self.value_delta, min_y + self.value_delta
        points = [
            (i, j)
            for i in range(min_x, max_x, self.step_size)
            for j in range(min_y, max_y, self.step_size)
        ]
        altis = RgeAltiClient().fetch_points(points)
        page = np.array(altis).reshape((self.page_size, self.page_size))
        return page


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
        self.attributes = {"alti": Alti(step_size)}

    @property
    def cell_area(self):
        return self.step_size**2

    def coords(self, cell):
        x, y = cell
        return (
            int(self.center.x + x * self.step_size),
            int(self.center.y + y * self.step_size),
        )

    def compute_runoff_surface(self, max_surface):
        """Find the total surface of the water runoof interception area.

        This is a very classic Breadth-first search algorithm.

        See https://www.redblobgames.com/pathfinding/a-star/introduction.html#breadth-first-search
        """

        start = (0, 0)
        frontier = Queue()
        frontier.put(start)
        reached = set()
        reached.add(start)
        reached_surface = 0

        self.randomize.cache_clear()

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
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if (dx, dy) != (0, 0):
                    yield (x + dx, y + dy)

    def is_flowing(self, from_cell, to_cell):
        """Does the water flows from cell 1 to cell 2?

        This is the most basic implementation of the D8 algorithm.
        Water flows entirely from one cell the cell around that as the
        deepest elevation deficit.

        See https://www.sigterritoires.fr/index.php/lhydrologie-avec-un-sig-pour-les-nuls-que-nous-sommes-calcul-de-lecoulement1/  # noqa
        """
        return self.lowest_alti_around(from_cell) == self.alti(to_cell)

    def lowest_alti_around(self, cell):
        altis = [self.alti(n) for n in self.neighbours(cell)]
        return min(altis)

    def alti(self, cell):
        val = self.attributes["alti"].get(self.coords(cell))
        return self.randomize(val)

    def randomize(self, val):
        delta = random.uniform(-0.2, 0.2)
        return val + delta


class Command(BaseCommand):
    """Calcule la surface dont l'eau ruisselle jusqu'à un point."""

    def add_arguments(self, parser):
        parser.add_argument("x", nargs=1, type=int)
        parser.add_argument("y", nargs=1, type=int)
        parser.add_argument("--step_size", nargs="?", type=int, default=10)
        parser.add_argument("--iterations", nargs="?", type=int, default=1)

    def handle(self, *args, **options):

        x = options["x"][0]
        y = options["y"][0]
        step_size = options["step_size"]
        iterations = options["iterations"]
        mnt = Mnt(x, y, step_size=step_size)

        surfaces = sorted(
            [mnt.compute_runoff_surface(MAX_SURFACE) for _ in range(iterations)]
        )
        print(surfaces)
        plt.hist(surfaces)
        plt.show()

        surface = statistics.mean(surfaces)
        self.stdout.write(f"Surface de ruissellement = {surface}m²")
