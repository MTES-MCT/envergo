import numpy as np
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


mnt = Mnt(ALTI)
mnt.compute_flow()


class Command(BaseCommand):
    def handle(self, *args, **options):

        zone = [(4, 4), (5, 4), (5, 5)]
        new_zone = zone
        surface = len(zone) * (MESH_SIZE ** 2)
        self.drawGrid([], new_zone)
        # breakpoint()

        while surface < MAX_SURFACE and len(new_zone) > 0:
            import time

            time.sleep(1)
            new_zone = self.expandZone(zone, new_zone)
            self.drawGrid(zone, new_zone)
            zone = zone + new_zone
            surface = len(zone) * (MESH_SIZE ** 2)
            # breakpoint()

    def expandZone(self, old_zone, zone):
        """Find all cells with water runing off into existing zone."""

        new_zone = []

        # For each cell in the project zone
        for x, y in zone:

            # Find nearby cells with flow direction pointing toward this cell
            window = mnt.window(x, y, 1)

            for i in range(-1, 2):
                for j in range(-1, 2):
                    coord_x = x + i
                    coord_y = y + j

                    if any(
                        (
                            i == j == 0,
                            coord_x < 0,
                            coord_x >= mnt.terrain.shape[0],
                            coord_y < 0,
                            coord_y >= mnt.terrain.shape[1],
                            (coord_x, coord_y) in old_zone,
                        )
                    ):
                        continue

                    direction = window[j + 1, i + 1]
                    dir_x, dir_y = DIRECTIONS[direction]
                    flow_x, flow_y = i + dir_x, j + dir_y
                    if flow_x == flow_y == 0:
                        new_zone += [(coord_x, coord_y)]

        return new_zone

    def drawGrid(self, zone, new_zone):
        print("\033c", end="")
        for y in range(0, mnt.terrain.shape[1]):
            for x in range(0, mnt.terrain.shape[0]):
                if (x, y) in new_zone:
                    print(
                        colored(f"{mnt.terrain[y][x][0]}", "white", "on_red"),
                        end="",
                    )
                    print(" ", end="")
                elif (x, y) in zone:
                    print(colored(f"{mnt.terrain[y][x][0]} ", "red"), end="")
                else:
                    print(colored(f"{mnt.terrain[y][x][0]} ", "green"), end="")
            print("")
