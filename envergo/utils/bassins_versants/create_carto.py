import warnings
from math import pi
from typing import List

import numpy as np
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


def calculate_bassin_versant_vectorized(
    params,
    current_tile,
    output_carto_precision,
    input_folder,
    tile_index=None,
):
    """Compute bassin versant for all output points in a tile using numpy vectorization.

    Instead of looping over individual points, this computes all ~62,500 output
    points simultaneously using numpy broadcasting and fancy indexing. Each
    (quadrant, radius) section is processed as a single array operation over all
    points, giving ~100-1000x speedup over the per-point loop.

    Args:
        params: bassinVersantParameters with algorithm settings.
        current_tile: Path to the center tile ASC file.
        output_carto_precision: Output grid spacing in meters.
        input_folder: Directory containing the input ASC tiles.
        tile_index: Optional pre-built tile index for fast neighbor lookup.

    Returns:
        Tuple of (result_array, output_info) where result_array is a 2D numpy
        array (nrows, ncols) of bassin versant values, and output_info is the
        header dict for the output ASC file.
    """
    querier = cartoQuerier(input_folder, current_tile, tile_index=tile_index)
    big_carto = querier.current_big_carto
    tile_info = querier.center_tile_info
    cellsize = tile_info["cellsize"]
    nrows = tile_info["nrows"]
    ncols = tile_info["ncols"]

    # Build the quadrant geometry (offsets in meters)
    inner_offsets_list, quadrant_offsets = carto.create_quadrants(
        params.carto_precision,
        params.inner_radius,
        params.radii,
        params.quadrants_nb,
    )
    inner_offsets = np.array(inner_offsets_list, dtype=np.int32)

    # Output grid dimensions
    out_width = round(params.carto_precision * ncols / output_carto_precision)
    out_height = round(params.carto_precision * nrows / output_carto_precision)
    step = round(output_carto_precision / cellsize)  # pixels between output points

    # Compute pixel positions of all output points in the big carto.
    # x_indices: 0..out_width-1, y_indices: 0..out_height-1
    # Output point (xi, yi) is at:
    #   col = xi * step + ncols
    #   row = 2*nrows - 1 - yi * step
    x_indices = np.arange(out_width)
    y_indices = np.arange(out_height)
    point_cols = x_indices * step + ncols  # shape (out_width,)
    point_rows = 2 * nrows - 1 - y_indices * step  # shape (out_height,)

    # Flatten to 1D arrays of all N = out_width * out_height points.
    # Points are ordered (y=0,x=0), (y=0,x=1), ..., (y=0,x=W-1), (y=1,x=0), ...
    # matching the original code's iteration order.
    grid_rows, grid_cols = np.meshgrid(point_rows, point_cols, indexing="ij")
    flat_rows = grid_rows.ravel()  # shape (N,)
    flat_cols = grid_cols.ravel()  # shape (N,)
    num_points = len(flat_rows)

    # Convert quadrant offsets from meters to pixel deltas.
    # Offset (ox, oy) in meters → col_delta = ox/cellsize, row_delta = -oy/cellsize
    inner_col_deltas = (inner_offsets[:, 0] / cellsize).astype(int)
    inner_row_deltas = (-inner_offsets[:, 1] / cellsize).astype(int)

    # Compute inner circle mean altitude for all points at once
    inner_mean = _vectorized_section_mean(
        big_carto, flat_rows, flat_cols, inner_row_deltas, inner_col_deltas
    )

    # Compute section means for all (quadrant, radius) combinations
    section_means = []
    for q in range(params.quadrants_nb):
        quad_means = []
        for r in range(len(params.radii)):
            offsets = quadrant_offsets[q][r]
            col_deltas = (offsets[:, 0] / cellsize).astype(int)
            row_deltas = (-offsets[:, 1] / cellsize).astype(int)
            mean = _vectorized_section_mean(
                big_carto, flat_rows, flat_cols, row_deltas, col_deltas
            )
            quad_means.append(mean)
        section_means.append(quad_means)

    # Vectorized bassin versant algorithm
    radii_ext = [0, params.inner_radius] + params.radii
    section_surfaces = np.array(
        [pi * radii_ext[r + 2] ** 2 - pi * radii_ext[r + 1] ** 2
         for r in range(len(params.radii))]
    )

    total_surface = np.zeros(num_points)
    for q in range(params.quadrants_nb):
        prev_alti = inner_mean.copy()
        still_active = np.ones(num_points, dtype=bool)
        for r in range(len(params.radii)):
            denom = radii_ext[r + 2] - radii_ext[r]
            slope_ok = (
                2 * (section_means[q][r] - prev_alti) / denom
            ) > params.slope
            still_active &= slope_ok
            total_surface += still_active * section_surfaces[r]
            prev_alti = np.where(still_active, section_means[q][r], prev_alti)

    result_flat = total_surface / params.quadrants_nb

    # Reshape to 2D output grid. y_indices go south-to-north (0=south), but
    # ASC format stores row 0 as the northernmost row, so flip vertically.
    result_array = result_flat.reshape(out_height, out_width)[::-1]

    bottom_left = (tile_info["x_range"][0], tile_info["y_range"][0])
    output_info = {
        "ncols": out_width,
        "nrows": out_height,
        "xllcorner": bottom_left[0],
        "yllcorner": bottom_left[1],
        "cellsize": output_carto_precision,
        "nodata_value": -99999.00,
    }

    return result_array, output_info


def _vectorized_section_mean(big_carto, point_rows, point_cols, row_deltas, col_deltas):
    """Compute the mean altitude of a section for all points simultaneously.

    For N output points and K offset positions in the section, builds an (N, K)
    lookup table via numpy broadcasting and computes the mean across the K axis.

    Args:
        big_carto: The 3×3 tile altitude array.
        point_rows: 1D array of row indices for all output points (N,).
        point_cols: 1D array of col indices for all output points (N,).
        row_deltas: 1D array of row offsets for this section (K,).
        col_deltas: 1D array of col offsets for this section (K,).

    Returns:
        1D array of mean altitudes, shape (N,).
    """
    lookup_rows = point_rows[:, None] + row_deltas[None, :]  # (N, K)
    lookup_cols = point_cols[:, None] + col_deltas[None, :]  # (N, K)
    altitudes = big_carto[lookup_rows, lookup_cols]  # (N, K)
    return np.mean(altitudes, axis=1)


def create_carto(
    params: bassinVersantParameters,
    current_tile: str,
    output_carto_precision: int,
    ouptut_file: str,
    input_folder: str,
    tile_index=None,
):
    """
    Crée une cartographie en calculant le bassin versant.

    Args:
        params (bassinVersantParameters): Paramètres pour le calcul du bassin versant.
        current_tile:  Tuile d'altimétrie pour laquelle calculer le bassin versant.
        output_carto_precision (int): Précision de la cartographie de sortie.
        ouptut_file (str): Fichier de sortie de la cartographie.
        input_folder (str): Dossier d'entrée.
        tile_index: Optional pre-built tile index for fast neighbor lookup.
    """
    result_array, output_info = calculate_bassin_versant_vectorized(
        params,
        current_tile,
        output_carto_precision,
        input_folder,
        tile_index=tile_index,
    )
    carto.save_array_to_carto(result_array, ouptut_file, output_info)
