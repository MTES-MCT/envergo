import warnings
from typing import List

from tqdm import tqdm
from utils import carto
from utils.bassin_versant import calculate_bassin_versant_one_point
from utils.carto_querier import cartoQuerier

warnings.filterwarnings("ignore")
# ignore when numpy is trying to do the mean of an empty slice


class bassinVersantParameters:
    def __init__(
        self,
        carto_precision: int,
        inner_radius: int,
        radii: List[int],
        quadrants_nb: int,
        slope: float,
    ):
        """
        Crée un objet avec les paramètres pour le calcul du bassin versant.

        Args:
            carto_precision (int): Précision de lecture de la cartographie d'altimétrie.
            inner_radius (int): Rayon interne.
            radii (List[int]): Liste des rayons.
            quadrants_nb (int): Nombre de quadrants.
            slope (float): Pente.
        """
        self.carto_precision = carto_precision
        self.inner_radius = inner_radius
        self.radii = radii
        self.quadrants_nb = quadrants_nb
        self.slope = slope

    def __str__(self):
        string_result = "parameters("
        string_result += f"carto_precision: {self.carto_precision}"
        string_result += f" - inner_radius: {self.inner_radius}"
        string_result += f" - radii: {self.radii}"
        string_result += f" - slope: {self.slope})"
        return string_result


def calculate_bassin_versant_on_points(
    points,
    params: bassinVersantParameters,
    current_tile,
    input_folder,
):
    """
    Calcule le bassin versant pour une liste de points donnés.

    Args:
        points: Liste des points.
        params (bassinVersantParameters): Paramètres pour le calcul du bassin versant.
        current_tile: Tuile d'altimétrie pour laquelle calculer le bassin versant.
        input_folder: Dossier d'entrée contenant les cartographies d'altimétrie.

    Returns:
        List: Liste des résultats du calcul du bassin versant pour chaque point.
    """
    results = []

    carto_machine = cartoQuerier(input_folder, current_tile)

    (
        origin_less_inner_circle_points,
        origin_less_quadrants_points,
    ) = carto.create_quadrants(
        params.carto_precision, params.inner_radius, params.radii, params.quadrants_nb
    )

    for point in tqdm(points, leave=False):
        if carto_machine.query_one_point(point) is not None:
            inner_circle_points = carto.update_origin(
                point, origin_less_inner_circle_points
            )

            quadrants = []
            for q in range(params.quadrants_nb):
                quadrants.append([])
                for i, _ in enumerate(params.radii):
                    quadrants[q].append([])
                    quadrants[q][i] = carto_machine.get_mean_alti(
                        carto.update_origin(point, origin_less_quadrants_points[q][i])
                    )

            inner_circle_alti = carto_machine.get_mean_alti(inner_circle_points)
            results.append(
                (
                    point,
                    calculate_bassin_versant_one_point(
                        inner_circle_alti,
                        quadrants,
                        params.inner_radius,
                        params.radii,
                        params.quadrants_nb,
                        params.slope,
                    ),
                )
            )

        else:
            results.append((point, None))

    return results


def create_carto(
    params: bassinVersantParameters,
    current_tile: str,
    output_carto_precision: int,
    ouptut_file: str,
    input_folder: str,
):
    """
    Crée une cartographie en calculant le bassin versant.

    Args:
        params (bassinVersantParameters): Paramètres pour le calcul du bassin versant.
        current_tile:  Tuile d'altimétrie pour laquelle calculer le bassin versant.
        output_carto_precision (int): Précision de la cartographie de sortie.
        ouptut_file (str): Fichier de sortie de la cartographie.
        input_folder (str): Dossier d'entrée.
    """
    bottom_left = carto.get_bottom_left_corner(current_tile)
    info = carto.get_carto_info(current_tile)
    width = round(params.carto_precision * info["ncols"] / output_carto_precision)
    height = round(params.carto_precision * info["nrows"] / output_carto_precision)

    points = []
    for y in range(height):
        for x in range(width):
            points.append(
                (
                    round(bottom_left[0] + x * output_carto_precision),
                    round(bottom_left[1] + y * output_carto_precision),
                )
            )

    res = calculate_bassin_versant_on_points(
        points,
        params,
        current_tile,
        input_folder,
    )

    carto.save_list_to_carto(
        res,
        ouptut_file,
        {
            "ncols": width,
            "nrows": height,
            "xllcorner": bottom_left[0],
            "yllcorner": bottom_left[1],
            "cellsize": output_carto_precision,
            "nodata_value": -99999.00,
        },
    )
