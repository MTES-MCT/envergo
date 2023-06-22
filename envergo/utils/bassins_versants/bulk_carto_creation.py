import argparse
import os
import warnings

from create_carto import bassinVersantParameters, create_carto
from tqdm import tqdm
from utils.carto import get_carto_info

warnings.filterwarnings("ignore")
# ignore when numpy is trying to do the mean of an empty slice


def bulk_carto_creation(input_folder, output_folder, output_carto_precision=20):
    print(f"\nRunning Bulk Carto Creator in {input_folder}...\n")

    # region parameters
    params = bassinVersantParameters(
        carto_precision=5,
        inner_radius=25,
        radii=[50, 75, 100, 130, 160],
        quadrants_nb=12,
        slope=0.05,
    )

    # endregion

    print(
        "progression : first bar is the number of cartos, second is the current carto creation"
    )
    for file in tqdm(os.listdir(input_folder)):
        info = get_carto_info(f"{input_folder}/{file}")
        bottom_left = (info["xllcorner"], info["yllcorner"])
        ouptut_file = (
            "{}/envergo_basssin_versant_fxx_{:04d}_{:04d}_mnt_lamb93.asc".format(
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
    parser = argparse.argument_parser(
        description="run a bulk carto creation for bassin versant."
    )
    parser.add_argument(
        "input_folder",
        type=str,
        help="the input folder in which to search for rge alti cartos",
    )
    parser.add_argument(
        "output_folder",
        type=str,
        help="the output folder in which to store the bassin versant cartos",
    )
    parser.add_argument(
        "--output-precision",
        dest="output_precision",
        default=20,
        help="the output precision of the carto, defaults to 20",
    )

    args = parser.parse_args()
    print(args.input_folder)
    print(args.output_folder)
    print(args.output_precision)

    bulk_carto_creation(
        args.input_folder,
        args.output_folder,
        output_carto_precision=args.output_precision,
    )
