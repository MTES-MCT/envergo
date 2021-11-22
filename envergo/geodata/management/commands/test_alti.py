import time

import numpy as np
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from termcolor import colored

# Small sample for the ALTI ign database
ALTI = [
    [509, 509, 520, 515, 513, 514, 515, 516, 518, 518],
    [515, 516, 517, 519, 520, 521, 522, 523, 510, 525],
    [517, 518, 519, 520, 521, 522, 524, 525, 526, 527],
    [512, 514, 515, 516, 518, 519, 520, 522, 522, 523],
    [511, 512, 513, 514, 515, 516, 517, 519, 520, 521],
    [504, 505, 506, 507, 520, 509, 510, 511, 512, 514],
    [520, 520, 521, 522, 525, 524, 525, 526, 527, 529],
    [506, 507, 509, 509, 525, 530, 525, 530, 515, 516],
    [498, 499, 501, 502, 542, 524, 535, 532, 534, 539],
    [501, 502, 503, 504, 525, 526, 507, 538, 538, 540],
]

MESH_SIZE = 1  # 1 block = 1m x 1m = 1m²

MAX_SURFACE = 30  # m²

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


WGS84_SRID = 4326  #


class Mnt:
    """Stores and gives access to some terrain properties.

    Mnt = Modèle Numérique de Terrain.

    The terrain is represented as a grid, centered on a single point.

    E.g, you can initialize a mnt centered on your house with a step of 10m.
    Then, the coordinates [0][0] represent your house, [0][1] is 10m south of
    you house, [100][0] is 1km east, etc.
    """

    def __init__(self, longitude, latitude, stepSize):
        """Initialize the Mnt."""

        self.center = Point(longitude, latitude, srid=WGS84_SRID)
        self.stepSize = stepSize

    @property
    def cellArea(self):
        return self.stepSize ** 2

    @property
    def bounds(self):
        return {
            "x_min": -100,
            "x_max": 100,
            "y_min": -100,
            "y_max": 100,
        }

    def coordinates(self, x, y):
        """Get coordinates for the grid indexed at x, y."""
        pass

    def altitude(self, x, y):
        pass

    def flow(self, x, y):
        pass

    def findCellsFlowingTo(self, x, y):
        """Find nearby cells with a slope pointing to the given cell.

        Returns a list of (x, y) grid coordinates tuples.
        """

        # # Find nearby cells with flow direction pointing toward this cell
        # window = self.mnt.window(x, y, 1)

        # for i in range(-1, 2):
        #     for j in range(-1, 2):
        #         coord_x = x + i
        #         coord_y = y + j

        #         if any(
        #             (
        #                 i == j == 0,
        #                 coord_x < 0,
        #                 coord_x >= self.mnt.terrain.shape[0],
        #                 coord_y < 0,
        #                 coord_y >= self.mnt.terrain.shape[1],
        #                 (coord_x, coord_y) in old_zone,
        #             )
        #         ):
        #             continue

        #         direction = window[j + 1, i + 1]
        #         dir_x, dir_y = DIRECTIONS[direction]
        #         flow_x, flow_y = i + dir_x, j + dir_y
        #         if flow_x == flow_y == 0:
        #             new_zone += [(coord_x, coord_y)]


class MntOld:
    """Modère Numérique de Terrain."""

    def __init__(self, altiGrid):

        self.terrain = np.stack(
            [altiGrid, np.zeros(shape=(10, 10), dtype="i4")], axis=2
        )

    def altitude(self, x, y):
        return self.terrain[y, x, 0]

    def direction(self, x, y):
        return self.terrain[y, x, 1]

    def window(self, x, y, dim=0):
        xmin = max(0, x - 1)
        xmax = min(self.terrain.shape[0], x + 2)
        ymin = max(0, y - 1)
        ymax = min(self.terrain.shape[1], y + 2)

        window = self.terrain[ymin:ymax, xmin:xmax, dim]  # noqa

        # Pad window at the edges
        before_x = 1 if y == 0 else 0
        after_x = 1 if y == self.terrain.shape[1] - 1 else 0
        before_y = 1 if x == 0 else 0
        after_y = 1 if x == self.terrain.shape[0] - 1 else 0
        window = np.pad(
            window,
            ((before_x, after_x), (before_y, after_y)),
            constant_values=999999,
        )

        return window

    def compute_flow(self):
        """Compute flow directions for all terrain cells."""

        # For each cell of the grid…
        for x in range(0, self.terrain.shape[0]):
            for y in range(0, self.terrain.shape[1]):

                # Extract a window of the nearby cells
                window = self.window(x, y)

                # Find the position of the cell with the lowest elevation.
                min_index = window.argmin()
                min_j, min_i = np.unravel_index(min_index, window.shape)

                # Give a numerical value to the flow direction
                direction = (min_i - 1, min_j - 1)
                dir_index = DIRECTIONS.index(direction)
                self.terrain[y, x, 1] = dir_index


class Command(BaseCommand):
    """Calcule la surface dont l'eau ruisselle jusqu'à un point."""

    def add_arguments(self, parser):
        parser.add_argument("longitude", nargs=1, type=float)
        parser.add_argument("latitude", nargs=1, type=float)

    def handle(self, *args, **options):

        longitude = options["longitude"][0]
        latitude = options["latitude"][0]
        self.mnt = Mnt(longitude, latitude, stepSize=10)

        zone = []
        new_zone = [(0, 0)]
        surface = len(new_zone) * self.mnt.cellArea
        # breakpoint()

        while surface < MAX_SURFACE and len(new_zone) > 0:
            self.drawGrid(zone, new_zone)
            new_zone = self.expandZone(zone, new_zone)
            zone = zone + new_zone
            surface = len(zone) * self.mnt.cellArea
            time.sleep(1)
            # breakpoint()

    def expandZone(self, old_zone, zone):
        """Find all cells with water runing off into existing zone."""

        new_zone = []

        for x, y in zone:
            cells = self.mnt.findCellsFlowingTo(x, y)
            for (cell_x, cell_y) in cells:
                if (cell_x, cell_y) not in old_zone:
                    new_zone.append([(cell_x, cell_y)])

        return new_zone

    def drawGrid(self, zone, new_zone):
        """Visually display an algo step."""

        print("\033c", end="")
        for y in range(self.mnt.bounds["y_min"], self.mnt.bounds["y_max"]):
            for x in range(0, self.mnt.bounds["x_min"], self.mnt.bounds["x_max"]):
                if (x, y) in new_zone:
                    print(
                        colored(f"{self.mnt.altitude(x, y)}", "white", "on_red"),
                        end="",
                    )
                    print(" ", end="")
                elif (x, y) in zone:
                    print(colored(f"{self.mnt.altitude(x, y)} ", "red"), end="")
                else:
                    print(colored(f"{self.mnt.altitude(x, y)} ", "green"), end="")
            print("")
