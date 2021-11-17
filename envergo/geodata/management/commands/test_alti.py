import numpy as np
from django.core.management.base import BaseCommand
from termcolor import colored

# Small sample for the ALTI ign database
ALTI = [
    [520, 520, 521, 522, 524, 524, 525, 526, 527, 529],
    [515, 516, 517, 519, 520, 521, 522, 523, 524, 525],
    [517, 518, 519, 520, 521, 522, 524, 525, 526, 527],
    [509, 509, 511, 512, 513, 514, 515, 516, 518, 518],
    [512, 514, 515, 516, 518, 519, 520, 522, 522, 523],
    [511, 512, 513, 514, 515, 516, 517, 519, 520, 521],
    [504, 505, 506, 507, 508, 509, 510, 511, 512, 514],
    [501, 502, 503, 504, 505, 506, 507, 508, 509, 510],
    [498, 499, 501, 502, 503, 504, 505, 506, 507, 508],
    [506, 507, 509, 509, 511, 511, 513, 514, 515, 516],
]
MNT = np.array(ALTI)

# DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

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


class Mnt:
    """Modère Numérique de Terrain."""

    def __init__(self, altiGrid):
        self.terrain = np.stack(
            [altiGrid, np.zeros(shape=(10, 10), dtype="i4")], axis=2
        )

    def altitude(self, x, y):
        return self.terrain[y, x, 0]

    def direction(self, x, y):
        return self.terrain[y, x, 1]

    def compute_flow(self):
        """Compute flow directions for all terrain cells."""

        # For each cell of the grid…
        for x in range(0, self.terrain.shape[0]):

            # Compute the size of the sliding window
            # We also handle the edges of the grid.
            xmin = max(0, x - 1)
            xmax = min(10, x + 2)

            for y in range(0, self.terrain.shape[1]):
                ymin = max(0, y - 1)
                ymax = min(10, y + 2)

                # Extract a window of the nearby cells
                window = self.terrain[ymin:ymax, xmin:xmax, 0]  # noqa

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

                # Find the position of the cell with the lowest elevation.
                min_index = window.argmin()
                min_j, min_i = np.unravel_index(min_index, window.shape)

                # Give a numerical value to the flow direction
                direction = (min_i - 1, min_j - 1)
                dir_index = DIRECTIONS.index(direction)
                self.terrain[y, x, 1] = dir_index


mnt = Mnt(ALTI)
mnt.compute_flow()
breakpoint()


class Command(BaseCommand):
    def handle(self, *args, **options):

        zone = [(4, 4), (4, 5), (5, 4), (5, 5)]
        new_zone = zone
        surface = len(zone) * (MESH_SIZE ^ 2)

        while surface < MAX_SURFACE and len(new_zone) > 0:
            new_zone = self.expandZone(zone, new_zone)
            zone = zone + new_zone
            surface = len(zone) * (MESH_SIZE ^ 2)
            self.drawGrid(zone)

    def expandZone(self, zone, new_zone):
        """Find all cells with water runing off into existing zone."""

        # Pour chaque cellule de la zone
        # for x, y in new_zone:

        #     # Pour chaque case autour de la cellule
        #     for dx in range(-1, 2):
        #         for dy in range(-1, 2):
        #             newx = x + dx
        #             newy = y + dy
        #             window = MNT[x - 1 : x + 2, y - 1 : y + 2]  # noqa
        #     # breakpoint()
        pass

    def drawGrid(self, zone):
        for y in range(10):
            for x in range(10):
                if (y, x) in zone:
                    print(colored(f"{MNT[y][x]} ", "green"), end="")
                else:
                    print(colored(f"{MNT[y][x]} ", "red"), end="")
            print("")
