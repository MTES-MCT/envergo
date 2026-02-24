import os

import numpy as np


def build_tile_index(carto_dir):
    """Pre-read all tile headers and build a coordinate-keyed lookup.

    Returns a dict mapping (x_range[0], y_range[0]) to the tile's info dict.
    This allows O(1) neighbor lookup in cartoQuerier instead of scanning every
    file for each tile processed.
    """
    index = {}
    for filename in os.listdir(carto_dir):
        filepath = os.path.join(carto_dir, filename)
        info = get_carto_info(filepath)
        key = (round(info["x_range"][0]), round(info["y_range"][0]))
        index[key] = info
    return index


def get_carto_info(file_name):
    """
    Obtient les informations de la cartographie à partir du nom de fichier, en analysant les headers.

    Args:
        file_name (str): Nom du fichier de la cartographie.

    Returns:
        dict: Informations de la cartographie.
    """
    info = {}
    with open(file_name) as f:
        info["file_name"] = file_name
        info["ncols"] = int(f.readline().split(" ")[-1])
        info["nrows"] = int(f.readline().split(" ")[-1])
        info["xllcorner"] = float(f.readline().split(" ")[-1])
        info["yllcorner"] = float(f.readline().split(" ")[-1])
        info["cellsize"] = float(f.readline().split(" ")[-1])
        info["nodata_value"] = float(f.readline().split(" ")[-1])
        info["x_range"] = (
            round(info["xllcorner"] + info["cellsize"] / 2),
            round(
                info["xllcorner"]
                + info["ncols"] * info["cellsize"]
                - info["cellsize"] / 2
            ),
        )
        info["y_range"] = (
            round(info["yllcorner"] - info["cellsize"] / 2),
            round(
                info["yllcorner"]
                + info["nrows"] * info["cellsize"]
                - info["cellsize"] * 3 / 2
            ),
        )
    return info


def load_carto(file_name):
    """
    Charge la cartographie à partir du fichier.

    Args:
        file_name (str): Nom du fichier de la cartographie.

    Returns:
        ndarray: Cartographie chargée.
    """
    info = get_carto_info(file_name)
    carto = np.loadtxt(file_name, skiprows=6)
    carto[carto == info["nodata_value"]] = np.nan
    return carto


def get_bottom_left_corner(carto_file_name):
    """
    Obtient le coin inférieur gauche de la cartographie à partir du nom du fichier.

    Args:
        carto_file_name (str): Nom du fichier de la cartographie.

    Returns:
        tuple: Coordonnées du coin inférieur gauche.
    """
    info = get_carto_info(carto_file_name)
    return (info["x_range"][0], info["y_range"][0])


def save_list_to_carto(data_list, file_name, info):
    """
    Enregistre une liste de données en une cartographie au format asc.

    Args:
        data_list (list): Liste de données à enregistrer.
        file_name (str): Nom du fichier de la cartographie.
        info (dict): Informations de la cartographie.
    """
    # Extraire les coordonnées et les altitudes séparément
    coordinates = [element[0] for element in data_list]
    altitudes = [element[1] for element in data_list]

    # Convertir les coordonnées et les altitudes en tableaux numpy
    coordinates_array = np.array(coordinates)
    altitudes_array = np.array(altitudes)

    # Créer un tableau numpy 2D avec les coordonnées comme indices et les altitudes comme valeurs
    x_coords, y_coords = coordinates_array.T
    num_x = len(np.unique(x_coords))
    num_y = len(np.unique(y_coords))
    result_array = np.zeros((num_y, num_x))
    x_indices = np.searchsorted(np.unique(x_coords), x_coords)
    y_indices = num_y - 1 - np.searchsorted(np.unique(y_coords), y_coords)
    result_array[y_indices, x_indices] = altitudes_array

    save_array_to_carto(
        np.reshape(result_array, (info["ncols"], info["nrows"])), file_name, info
    )


def save_array_to_carto(array, file_name, info):
    """
    Enregistre un tableau numpy en une cartographie au format asc.

    Args:
        array (ndarray): Tableau à enregistrer.
        file_name (str): Nom du fichier de la cartographie.
        info (dict): Informations de la cartographie.
    """
    header = "ncols     %s\n" % info["ncols"]
    header += "nrows    %s\n" % info["nrows"]
    header += "xllcorner %s\n" % info["xllcorner"]
    header += "yllcorner %s\n" % info["yllcorner"]
    header += "cellsize %s\n" % info["cellsize"]
    header += "nodata_value %s\n" % info["nodata_value"]
    array[np.isnan(array) | (array is None)] = float(info["nodata_value"])

    np.savetxt(file_name, array, header=header, fmt="%1.2f", comments="")


def create_quadrants(carto_precision, inner_radius, radii, quadrants_nb):
    """
    Crée les quadrants pour un calcul de bassin versant.

    Args:
        carto_precision (float): Précision de la cartographie.
        inner_radius (float): Rayon intérieur.
        radii (list): Liste des rayons.
        quadrants_nb (int): Nombre de quadrants.

    Returns:
        tuple: Points du cercle intérieur et liste de liste des coordonnées des points de chaque partie de quadrant, avec une origine à (0,0).
    """
    quarter_points_nb = int(np.ceil(radii[-1] / carto_precision))
    quadrants_bins = np.linspace(0, 2 * np.pi, quadrants_nb + 1)
    quadrants = [[[] for _ in range(len(radii))] for _ in range(quadrants_nb)]
    inner_alti_points = []

    points = np.mgrid[
        -quarter_points_nb : quarter_points_nb + 1,
        -quarter_points_nb : quarter_points_nb + 1,
    ]
    displacements = carto_precision * points
    new_points = displacements[0] + 1j * displacements[1]

    # Trouver le 'donut' correspondant à chaque point
    distances = np.abs(new_points)
    radius_nbs = np.searchsorted(
        np.concatenate(([inner_radius], radii, [np.inf])), distances
    )

    # Trouver le quadrant pour chaque point
    angles = np.angle(new_points) % (2 * np.pi)
    quad_nbs = np.digitize(angles, quadrants_bins) - 1

    # Traiter les points en fonction de leur quadrant et rayon en utilisant les masques
    for quad_nb in range(quadrants_nb):
        for radius_nb in range(len(radii)):
            mask = np.logical_and(quad_nbs == quad_nb, radius_nbs == radius_nb + 1)
            quad_points = new_points[mask]
            quadrants[quad_nb][radius_nb].extend(
                zip(
                    np.round(quad_points.real).astype(int),
                    np.round(quad_points.imag).astype(int),
                )
            )
            # Convertir les points étendus en un tableau num_py
            quadrants[quad_nb][radius_nb] = np.array(
                quadrants[quad_nb][radius_nb], dtype=np.int32
            )

    inner_points = np.array(new_points[radius_nbs == 0])
    inner_alti_points.extend(
        zip(
            np.round(inner_points.real).astype(int),
            np.round(inner_points.imag).astype(int),
        )
    )

    return inner_alti_points, quadrants


def update_origin(origin, points):
    """
    Met à jour l'origine des points.

    Args:
        origin (ndarray): Origine.
        points (ndarray): Points à mettre à jour.

    Returns:
        ndarray: Points mis à jour, dans un nouveau tableau.
    """
    return np.add(points, origin)
