import os

import numpy as np
from utils import carto


class cartoQuerier:
    def __init__(self, carto_dir, tile):
        """
        Initialise un objet cartoQuerier, dont on se sert ensuite pour obtenir les altitudes moyennes de points.

        Args:
            carto_dir (str): Répertoire contenant les cartographies.
            tile (str): Nom du fichier de la tuile centrale.
        """
        self.center_tile_info = carto.get_carto_info(tile)
        center_tile = carto.load_carto(self.center_tile_info["file_name"])

        # Crée une "big carto" de forme 3x3 tuiles
        self.current_big_carto = np.zeros_like(
            np.repeat(np.repeat(center_tile, 3, axis=0), 3, axis=1)
        )

        def get_carto_coords(current_info):
            # Détermine les coordonnées de la tuile dans la "big carto"
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

        # Trouve les tuiles voisines et les ajoute à la "big carto"
        for file in os.listdir(carto_dir):
            file_name = f"{carto_dir}/{file}"
            current_info = carto.get_carto_info(file_name)
            x_coord, y_coord = get_carto_coords(current_info)

            # Vérifie si nous sommes dans le voisinage de la tuile centrale et ajoute la carto à la "big carto" si c'est le cas.
            if x_coord in [0, 1, 2] and y_coord in [0, 1, 2]:
                y_min = y_coord * self.center_tile_info["nrows"]
                y_max = (y_coord + 1) * self.center_tile_info["nrows"]
                x_min = x_coord * self.center_tile_info["ncols"]
                x_max = (x_coord + 1) * self.center_tile_info["ncols"]

                self.current_big_carto[y_min:y_max, x_min:x_max] = carto.load_carto(
                    file_name
                )

    def get_mean_alti(self, points):
        """
        Obtient l'altitude moyenne des points.

        Args:
            points (ndarray): Coordonnées des points.

        Returns:
            float: Altitude moyenne des points.
        """
        points_coordinates = self.fit_to_big_carto(points)
        points_coordinates = points_coordinates.astype(int)
        return np.mean(
            self.current_big_carto[points_coordinates[:, 0], points_coordinates[:, 1]]
        )

    def fit_to_big_carto(self, points):
        """
        Ajuste les coordonnées des points à la "big carto".

        Args:
            points (ndarray): Coordonnées des points.

        Returns:
            ndarray: Coordonnées ajustées des points dans la "big carto".
        """
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
        """
        Interroge la "big carto" pour obtenir l'altitude d'un point.

        Args:
            point (tuple): Coordonnées du point.

        Returns:
            float: Altitude du point dans la "big carto".
        """
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
