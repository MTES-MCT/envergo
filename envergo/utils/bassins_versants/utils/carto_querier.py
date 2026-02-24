import os

import numpy as np
from utils import carto


class cartoQuerier:
    """Load a center tile and its 8 neighbors into a 3×3 'big carto' array.

    The big carto allows computing bassin versant for points near tile edges
    by providing access to altitude data from neighboring tiles.
    """

    def __init__(self, carto_dir, tile, tile_index=None):
        """Initialise the querier for a given center tile.

        Args:
            carto_dir: Directory containing the ASC tile files.
            tile: Path to the center tile file.
            tile_index: Optional pre-built coordinate-keyed dict from
                ``carto.build_tile_index``. When provided, neighbor lookup is
                O(1) instead of scanning every file in carto_dir.
        """
        self.center_tile_info = carto.get_carto_info(tile)
        center_tile = carto.load_carto(self.center_tile_info["file_name"])

        nrows = self.center_tile_info["nrows"]
        ncols = self.center_tile_info["ncols"]
        cellsize = self.center_tile_info["cellsize"]

        # Create a big carto of shape (3*nrows, 3*ncols), initialized to zero.
        # Unloaded neighbor regions stay at zero.
        self.current_big_carto = np.zeros(
            (3 * nrows, 3 * ncols), dtype=center_tile.dtype
        )

        if tile_index is not None:
            self._load_neighbors_from_index(
                tile_index, center_tile, nrows, ncols, cellsize
            )
        else:
            self._load_neighbors_by_scan(carto_dir, center_tile, nrows, ncols)

    def _load_neighbors_from_index(
        self, tile_index, center_tile, nrows, ncols, cellsize
    ):
        """Find and load neighbor tiles using the pre-built coordinate index."""
        cx = round(self.center_tile_info["x_range"][0])
        cy = round(self.center_tile_info["y_range"][0])
        tile_width = round(ncols * cellsize)
        tile_height = round(nrows * cellsize)

        for grid_x in range(3):
            for grid_y in range(3):
                dx = grid_x - 1  # -1, 0, +1
                dy = grid_y - 1  # -1, 0, +1
                key = (cx + dx * tile_width, cy + dy * tile_height)
                info = tile_index.get(key)
                if info is None:
                    continue

                # grid_y=0 → bottom neighbor (row slot 2), grid_y=2 → top (row slot 0)
                row_slot = 2 - grid_y
                col_slot = grid_x

                y_min = row_slot * nrows
                y_max = y_min + nrows
                x_min = col_slot * ncols
                x_max = x_min + ncols

                if dx == 0 and dy == 0:
                    tile_data = center_tile
                else:
                    tile_data = carto.load_carto(info["file_name"])

                self.current_big_carto[y_min:y_max, x_min:x_max] = tile_data

    def _load_neighbors_by_scan(self, carto_dir, center_tile, nrows, ncols):
        """Find and load neighbor tiles by scanning the directory (legacy path)."""
        for filename in os.listdir(carto_dir):
            file_path = os.path.join(carto_dir, filename)
            current_info = carto.get_carto_info(file_path)
            x_coord, y_coord = self._get_carto_coords(current_info)

            if x_coord in (0, 1, 2) and y_coord in (0, 1, 2):
                y_min = y_coord * nrows
                y_max = y_min + nrows
                x_min = x_coord * ncols
                x_max = x_min + ncols

                self.current_big_carto[y_min:y_max, x_min:x_max] = carto.load_carto(
                    file_path
                )

    def _get_carto_coords(self, current_info):
        """Determine the (col, row) grid position of a tile relative to center.

        Returns (-1, -1) if the tile is not a direct neighbor.
        """
        cellsize = self.center_tile_info["cellsize"]
        cx = self.center_tile_info["x_range"]
        cy = self.center_tile_info["y_range"]

        x_coord = -1
        if current_info["x_range"][1] + cellsize == cx[0]:
            x_coord = 0
        elif current_info["x_range"][0] == cx[0]:
            x_coord = 1
        elif current_info["x_range"][0] == cx[1] + cellsize:
            x_coord = 2

        y_coord = -1
        if current_info["y_range"][1] + cellsize == cy[0]:
            y_coord = 2
        elif current_info["y_range"][0] == cy[0]:
            y_coord = 1
        elif current_info["y_range"][0] == cy[1] + cellsize:
            y_coord = 0

        return x_coord, y_coord

    def get_mean_alti(self, points):
        """Return the mean altitude for a set of absolute-coordinate points.

        Args:
            points: Array of shape (K, 2) with (x, y) in meters.

        Returns:
            Mean altitude as a float. NaN if any sampled cell is NaN.
        """
        pixel_coords = self.fit_to_big_carto(points).astype(int)
        return np.mean(
            self.current_big_carto[pixel_coords[:, 0], pixel_coords[:, 1]]
        )

    def fit_to_big_carto(self, points):
        """Convert absolute (x, y) meter coordinates to (row, col) pixel indices.

        Args:
            points: Array of shape (K, 2) with (x_meters, y_meters).

        Returns:
            Array of shape (K, 2) with (row, col) in the big carto.
        """
        cellsize = self.center_tile_info["cellsize"]
        ncols = self.center_tile_info["ncols"]
        nrows = self.center_tile_info["nrows"]
        x0 = self.center_tile_info["x_range"][0]
        y0 = self.center_tile_info["y_range"][0]

        new_x = np.round((points[:, 0] - x0) / cellsize) + ncols
        new_y = np.round(nrows - (points[:, 1] - y0) / cellsize) - 1 + nrows
        return np.column_stack((new_y, new_x))

    def query_one_point(self, point):
        """Return the altitude of a single point from the big carto.

        Args:
            point: Tuple (x, y) in meters.

        Returns:
            Altitude value (float or NaN).
        """
        cellsize = self.center_tile_info["cellsize"]
        ncols = self.center_tile_info["ncols"]
        nrows = self.center_tile_info["nrows"]
        x0 = self.center_tile_info["x_range"][0]
        y0 = self.center_tile_info["y_range"][0]

        new_x = round((point[0] - x0) / cellsize) + ncols
        new_y = round(nrows - (point[1] - y0) / cellsize) - 1 + nrows
        return self.current_big_carto[new_y, new_x]
