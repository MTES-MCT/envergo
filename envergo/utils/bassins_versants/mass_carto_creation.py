import argparse
import os
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed

from create_carto import bassinVersantParameters, create_carto
from tqdm import tqdm
from utils.carto import build_tile_index, get_carto_info

warnings.filterwarnings("ignore")
# ignore when numpy is trying to do the mean of an empty slice


# Default algorithm parameters — decided after the comparative study
# (see parameters_benchmark.py).
DEFAULT_PARAMS = bassinVersantParameters(
    carto_precision=5,
    # Best input precision available from these maps
    inner_radius=25,
    # Inner surface ~2000 m², matching average project size on EnverGo
    radii=[59, 81, 98, 113, 126, 138, 149, 160],
    # Best set of radii from benchmark
    quadrants_nb=12,
    # Best quadrant count: more is too radial, fewer is imprecise
    slope=0.05,
    # Slope threshold for counting as bassin versant
)


def _make_output_path(output_folder, bottom_left):
    """Build the output ASC file path from the tile's bottom-left coordinates."""
    return "{}/ENVERGO_BASSSIN_VERSANT_FXX_{:04d}_{:04d}_MNT_LAMB93.ASC".format(
        output_folder,
        round(bottom_left[0] / 1000),
        round(bottom_left[1] / 1000),
    )


def _process_one_tile(tile_path, input_folder, output_folder, output_precision, tile_index):
    """Process a single tile: compute bassin versant and write the output ASC.

    This is the unit of work for both sequential and parallel execution.
    Returns the output file path on success.
    """
    info = get_carto_info(tile_path)
    bottom_left = (info["xllcorner"], info["yllcorner"])
    output_file = _make_output_path(output_folder, bottom_left)

    if os.path.exists(output_file):
        return None  # Already processed

    create_carto(
        DEFAULT_PARAMS,
        tile_path,
        output_precision,
        output_file,
        input_folder,
        tile_index=tile_index,
    )
    return output_file


def _process_one_tile_unpack(args):
    """Wrapper for ProcessPoolExecutor that unpacks the argument tuple.

    tile_index is NOT passed across processes — each worker rebuilds it
    would be expensive. Instead, we pass None and let cartoQuerier fall back
    to directory scanning. For the parallel path, the tile_index optimization
    is less critical since the I/O is overlapped with computation.
    """
    tile_path, input_folder, output_folder, output_precision = args
    return _process_one_tile(tile_path, input_folder, output_folder, output_precision, tile_index=None)


def mass_carto_creation(input_folder, output_folder, output_carto_precision=20, workers=1):
    """Compute bassin versant maps for every tile in the input folder.

    Args:
        input_folder: Directory containing the input RGE ALTI ASC tiles.
        output_folder: Directory where output bassin versant ASCs are written.
        output_carto_precision: Output grid spacing in meters (default 20).
        workers: Number of parallel worker processes. 1 = sequential.
    """
    print("\n\n")
    print("========= mass carto creation =========")
    print(f"\nRunning Mass Carto Creator in {input_folder}...")
    print(f"Workers: {workers}\n")

    tile_files = sorted(
        os.path.join(input_folder, f)
        for f in os.listdir(input_folder)
        if f.endswith((".asc", ".ASC"))
    )

    # Filter out tiles that already have output
    pending = []
    for tile_path in tile_files:
        info = get_carto_info(tile_path)
        bottom_left = (info["xllcorner"], info["yllcorner"])
        output_file = _make_output_path(output_folder, bottom_left)
        if not os.path.exists(output_file):
            pending.append(tile_path)

    print(f"Total tiles: {len(tile_files)}, pending: {len(pending)}\n")

    if not pending:
        print("Nothing to do — all tiles already processed.")
        return

    if workers <= 1:
        # Sequential path: build tile index once, reuse across all tiles
        print("Building tile index...")
        tile_index = build_tile_index(input_folder)
        print(f"  {len(tile_index)} tiles indexed.\n")

        for tile_path in tqdm(pending, desc="Tiles"):
            _process_one_tile(
                tile_path, input_folder, output_folder,
                output_carto_precision, tile_index,
            )
    else:
        # Parallel path: each worker scans the directory itself.
        # The overhead of repeated directory scans is negligible compared to
        # the computation savings from parallelism.
        args_list = [
            (tile_path, input_folder, output_folder, output_carto_precision)
            for tile_path in pending
        ]
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_process_one_tile_unpack, args): args[0]
                for args in args_list
            }
            with tqdm(total=len(futures), desc="Tiles") as pbar:
                for future in as_completed(futures):
                    future.result()  # Raise if the worker failed
                    pbar.update(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run a mass carto creation for bassin versant."
    )
    parser.add_argument(
        "--input-folder",
        dest="input_folder",
        type=str,
        required=True,
        help="The input folder with RGE ALTI ASC tiles.",
    )
    parser.add_argument(
        "--output-folder",
        dest="output_folder",
        type=str,
        required=True,
        help="The output folder for bassin versant ASC tiles.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count(),
        help="Number of parallel worker processes (default: number of CPUs).",
    )

    args = parser.parse_args()
    print(f"Input:  {args.input_folder}")
    print(f"Output: {args.output_folder}")
    print(f"Workers: {args.workers}")

    mass_carto_creation(
        args.input_folder,
        args.output_folder,
        workers=args.workers,
    )
