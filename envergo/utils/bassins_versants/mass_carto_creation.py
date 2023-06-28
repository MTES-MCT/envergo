import argparse
import os
import warnings

from create_carto import bassinVersantParameters, create_carto
from tqdm import tqdm
from utils.carto import get_carto_info

warnings.filterwarnings("ignore")
# ignore when numpy is trying to do the mean of an empty slice


def mass_carto_creation(input_folder, output_folder, output_carto_precision=20):
    """
    Crée une cartographie de bassin versant par cartographie d'altimétrie présente dans le dossier d'entrée.

    Args:
        input_folder (str): Le dossier d'entrée dans lequel rechercher les cartographies d'altitudes.
        output_folder (str): Le dossier de sortie dans lequel stocker les cartographies du bassin versant.
        output_carto_precision (int): La précision de la cartographie de sortie (par défaut : 20m car suffisant).
    """

    # region parameters
    params = bassinVersantParameters(
        carto_precision=5,
        inner_radius=25,
        radii=[50, 75, 100, 130, 160],
        quadrants_nb=12,
        slope=0.05,
    )

    # endregion
    print("\n\n")
    print("========= mass carto creation =========")
    print(f"\nRunning Mass Carto Creator in {input_folder}...\n\n")
    print(
        "progression : first bar is the number of cartos, second is the current carto creation"
    )
    for file in tqdm(os.listdir(input_folder)):
        info = get_carto_info(f"{input_folder}/{file}")
        bottom_left = (info["xllcorner"], info["yllcorner"])
        ouptut_file = (
            "{}/ENVERGO_BASSSIN_VERSANT_FXX_{:04d}_{:04d}_MNT_LAMB93.ASC".format(
                output_folder,
                round(bottom_left[0] / 1000),
                round(bottom_left[1] / 1000),
            )
        )

        create_carto(
            params,
            f"{input_folder}/{file}",
            output_carto_precision,
            ouptut_file,
            input_folder,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="run a mass carto creation for bassin versant."
    )
    parser.add_argument(
        "--input-folder",
        dest="input_folder",
        type=str,
        required=True,
        help="the input folder in which to search for rge alti cartos",
    )
    parser.add_argument(
        "--output-folder",
        dest="output_folder",
        type=str,
        required=True,
        help="the output folder in which to store the bassin versant cartos",
    )

    args = parser.parse_args()
    print(args.input_folder)
    print(args.output_folder)

    mass_carto_creation(
        args.input_folder,
        args.output_folder,
    )
