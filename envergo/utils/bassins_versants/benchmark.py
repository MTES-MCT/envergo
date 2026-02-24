"""Benchmark old vs. new bassin versant computation.

Usage:
    python benchmark.py --input-folder <rge_alti_dir> --tiles 3 --mode both
    python benchmark.py --input-folder ../../rgealti/dept_87 --mode new --tiles 5
"""

import argparse
import os
import time

from create_carto import (
    bassinVersantParameters,
    calculate_bassin_versant_on_points,
    calculate_bassin_versant_vectorized,
)
from utils.carto import build_tile_index, get_bottom_left_corner, get_carto_info

# Default parameters matching mass_carto_creation.py
DEFAULT_PARAMS = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=[59, 81, 98, 113, 126, 138, 149, 160],
    quadrants_nb=12,
    slope=0.05,
)
DEFAULT_OUTPUT_PRECISION = 20


def run_old(tile_path, input_folder):
    """Run the original per-point loop and return wall-clock time in seconds."""
    info = get_carto_info(tile_path)
    bottom_left = get_bottom_left_corner(tile_path)
    width = round(
        DEFAULT_PARAMS.carto_precision * info["ncols"] / DEFAULT_OUTPUT_PRECISION
    )
    height = round(
        DEFAULT_PARAMS.carto_precision * info["nrows"] / DEFAULT_OUTPUT_PRECISION
    )

    points = []
    for y in range(height):
        for x in range(width):
            points.append(
                (
                    round(bottom_left[0] + x * DEFAULT_OUTPUT_PRECISION),
                    round(bottom_left[1] + y * DEFAULT_OUTPUT_PRECISION),
                )
            )

    start = time.perf_counter()
    calculate_bassin_versant_on_points(
        points, DEFAULT_PARAMS, tile_path, input_folder
    )
    elapsed = time.perf_counter() - start
    return elapsed


def run_new(tile_path, input_folder, tile_index):
    """Run the vectorized computation and return wall-clock time in seconds."""
    start = time.perf_counter()
    calculate_bassin_versant_vectorized(
        DEFAULT_PARAMS,
        tile_path,
        DEFAULT_OUTPUT_PRECISION,
        input_folder,
        tile_index=tile_index,
    )
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark bassin versant computation."
    )
    parser.add_argument(
        "--input-folder", required=True,
        help="Directory with input RGE ALTI ASC tiles.",
    )
    parser.add_argument(
        "--tiles", type=int, default=3,
        help="Number of tiles to process.",
    )
    parser.add_argument(
        "--mode", choices=["old", "new", "both"], default="both",
        help="Which implementation to benchmark.",
    )
    args = parser.parse_args()

    tile_files = sorted(
        os.path.join(args.input_folder, f)
        for f in os.listdir(args.input_folder)
        if f.endswith((".asc", ".ASC"))
    )
    tile_files = tile_files[: args.tiles]

    print(f"Benchmarking {len(tile_files)} tiles, mode={args.mode}\n")

    tile_index = None
    if args.mode in ("new", "both"):
        print("Building tile index...")
        tile_index = build_tile_index(args.input_folder)
        print(f"  {len(tile_index)} tiles indexed.\n")

    old_times = []
    new_times = []

    for i, tile_path in enumerate(tile_files):
        label = os.path.basename(tile_path)
        print(f"[{i + 1}/{len(tile_files)}] {label}")

        if args.mode in ("old", "both"):
            t = run_old(tile_path, args.input_folder)
            old_times.append(t)
            print(f"  old: {t:.2f}s")

        if args.mode in ("new", "both"):
            t = run_new(tile_path, args.input_folder, tile_index)
            new_times.append(t)
            print(f"  new: {t:.2f}s")

        if args.mode == "both" and old_times and new_times:
            ratio = old_times[-1] / new_times[-1]
            print(f"  speedup: {ratio:.0f}x")

    print("\n--- Summary ---")
    if old_times:
        total_old = sum(old_times)
        print(f"Old total: {total_old:.2f}s  (avg {total_old / len(old_times):.2f}s/tile)")
    if new_times:
        total_new = sum(new_times)
        print(f"New total: {total_new:.2f}s  (avg {total_new / len(new_times):.2f}s/tile)")
    if old_times and new_times:
        print(f"Overall speedup: {sum(old_times) / sum(new_times):.0f}x")


if __name__ == "__main__":
    main()
