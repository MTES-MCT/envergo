import os

import numpy as np
from utils import carto


class cartoQuerier:
    def __init__(self, carto_dir, tile):
        self.center_tile_info = carto.get_carto_info(tile)
        center_tile = carto.load_carto(self.center_tile_info["file_name"])

        # create a "big carto" of shape 3x3 tiles
        self.current_big_carto = np.zeros_like(
            np.repeat(np.repeat(center_tile, 3, axis=0), 3, axis=1)
        )

        def get_carto_coords(current_info):
            x_coord = -1
            y_coord = -1
            if (
                current_info["x_range"][1] + self.center_tile_info["cellsize"]
                == self.center_tile_info["x_range"][0]
            ):
                x_coord = 0
            elif current_info["x_range"][0] == self.center_tile_info["x_range"][0]:
                x_coord = 1
            elif (
                current_info["x_range"][0]
                == self.center_tile_info["x_range"][1]
                + self.center_tile_info["cellsize"]
            ):
                x_coord = 2

            if (
                current_info["y_range"][1] + self.center_tile_info["cellsize"]
                == self.center_tile_info["y_range"][0]
            ):
                y_coord = 2
            elif current_info["y_range"][0] == self.center_tile_info["y_range"][0]:
                y_coord = 1
            elif (
                current_info["y_range"][0]
                == self.center_tile_info["y_range"][1]
                + self.center_tile_info["cellsize"]
            ):
                y_coord = 0

            return x_coord, y_coord

        # find the neigbor tiles and add them to the big_carto
        for file in os.listdir(carto_dir):
            current_info = carto.get_carto_info(carto_dir + "/" + file)
            x_coord, y_coord = get_carto_coords(current_info)

            # checking if we are in the neighborhood of the middle tile, and adding the carto to the big tile if so.
            if x_coord in [0, 1, 2] and y_coord in [0, 1, 2]:
                y_min = y_coord * self.center_tile_info["nrows"]
                y_max = (y_coord + 1) * self.center_tile_info["nrows"]
                x_min = x_coord * self.center_tile_info["ncols"]
                x_max = (x_coord + 1) * self.center_tile_info["ncols"]

                self.current_big_carto[y_min:y_max, x_min:x_max] = carto.load_carto(
                    carto_dir + "/" + file
                )

    def get_mean_alti(self, points):
        points_coordinates = self.fit_to_big_carto(points)
        points_coordinates = points_coordinates.astype(int)
        return np.mean(
            self.current_big_carto[points_coordinates[:, 0], points_coordinates[:, 1]]
        )

    def fit_to_big_carto(self, points):
        new_x = (
            np.round(
                (points[:, 0] - self.center_tile_info["x_range"][0])
                / self.center_tile_info["cellsize"]
            )
            + self.center_tile_info["ncols"]
        )
        new_y = (
            np.round(
                self.center_tile_info["nrows"]
                - (points[:, 1] - self.center_tile_info["y_range"][0])
                / self.center_tile_info["cellsize"]
            )
            - 1
            + self.center_tile_info["nrows"]
        )
        return np.column_stack((new_y, new_x))

    def query_one_point(self, point):
        new_x = (
            round(
                (point[0] - self.center_tile_info["x_range"][0])
                / self.center_tile_info["cellsize"]
            )
            + self.center_tile_info["ncols"]
        )
        new_y = (
            round(
                self.center_tile_info["nrows"]
                - (point[1] - self.center_tile_info["y_range"][0])
                / self.center_tile_info["cellsize"]
            )
            - 1
            + self.center_tile_info["nrows"]
        )
        return self.current_big_carto[new_y, new_x]
