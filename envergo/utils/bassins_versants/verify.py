"""Compare vectorized bassin versant output against reference ASC files.

Usage:
    python verify.py --input-folder <rge_alti_dir> --reference-folder <ref_dir>
    python verify.py --input-folder ../../rgealti/dept_87 \
                     --reference-folder ../../altis/dept_87 --tiles 5
"""

import argparse
import os
import sys

import numpy as np
from create_carto import bassinVersantParameters, calculate_bassin_versant_vectorized
from utils.carto import build_tile_index, get_carto_info, load_carto

# Default parameters matching mass_carto_creation.py
DEFAULT_PARAMS = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=[59, 81, 98, 113, 126, 138, 149, 160],
    quadrants_nb=12,
    slope=0.05,
)
DEFAULT_OUTPUT_PRECISION = 20


def find_input_tile_for_reference(reference_file, input_folder, tile_index):
    """Find the input tile that corresponds to a reference output file.

    The reference file's grid coordinates must fall within one of the input
    tiles. Returns the input tile path, or None if no match is found.
    """
    ref_info = get_carto_info(reference_file)
    ref_x = ref_info["xllcorner"]
    ref_y = ref_info["yllcorner"]

    for (tile_x, tile_y), info in tile_index.items():
        # Output xllcorner = x_range[0], yllcorner = y_range[0]
        if round(info["x_range"][0]) == round(ref_x) and round(info["y_range"][0]) == round(ref_y):
            return info["file_name"]

    return None


def verify_tile(input_tile, reference_file, tile_index, tolerance):
    """Run the vectorized computation on one tile and compare to reference.

    Returns a dict with comparison statistics, or None if the input tile
    could not be found.
    """
    result_array, _ = calculate_bassin_versant_vectorized(
        DEFAULT_PARAMS,
        input_tile,
        DEFAULT_OUTPUT_PRECISION,
        os.path.dirname(input_tile),
        tile_index=tile_index,
    )

    ref_info = get_carto_info(reference_file)
    ref_data = load_carto(reference_file)
    nodata = ref_info["nodata_value"]

    # In reference data, nodata cells are NaN (load_carto converts them).
    # In our result, those cells will be 0.0 (no bassin versant computed).
    # Mask them out for comparison — only compare cells that have valid
    # reference values.
    ref_flat = ref_data.ravel()
    res_flat = result_array.ravel()

    valid_mask = ~np.isnan(ref_flat)
    ref_valid = ref_flat[valid_mask]
    res_valid = res_flat[valid_mask]

    if len(ref_valid) == 0:
        return {"status": "skip", "reason": "all nodata"}

    abs_diff = np.abs(res_valid - ref_valid)
    max_err = float(np.max(abs_diff))
    mean_err = float(np.mean(abs_diff))
    exact_pct = float(np.mean(abs_diff == 0) * 100)
    within_tol_pct = float(np.mean(abs_diff <= tolerance) * 100)
    total_cells = len(ref_valid)
    nodata_cells = int(np.sum(~valid_mask))

    return {
        "status": "pass" if within_tol_pct == 100.0 else "fail",
        "max_error": max_err,
        "mean_error": mean_err,
        "exact_match_pct": exact_pct,
        "within_tolerance_pct": within_tol_pct,
        "total_cells": total_cells,
        "nodata_cells": nodata_cells,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Verify vectorized bassin versant against reference output."
    )
    parser.add_argument(
        "--input-folder", required=True,
        help="Directory with input RGE ALTI ASC tiles.",
    )
    parser.add_argument(
        "--reference-folder", required=True,
        help="Directory with reference output ASC tiles.",
    )
    parser.add_argument(
        "--tiles", type=int, default=0,
        help="Max number of tiles to verify (0 = all).",
    )
    parser.add_argument(
        "--tolerance", type=float, default=0.01,
        help="Absolute tolerance for floating-point comparison.",
    )
    args = parser.parse_args()

    print("Building tile index...")
    tile_index = build_tile_index(args.input_folder)
    print(f"  {len(tile_index)} input tiles indexed.")

    # Collect reference ASC files
    ref_files = sorted(
        f for f in os.listdir(args.reference_folder) if f.endswith(".ASC")
    )
    if args.tiles > 0:
        ref_files = ref_files[: args.tiles]

    print(f"Verifying {len(ref_files)} tiles (tolerance={args.tolerance})...\n")

    all_pass = True
    for i, ref_name in enumerate(ref_files):
        ref_path = os.path.join(args.reference_folder, ref_name)
        input_tile = find_input_tile_for_reference(ref_path, args.input_folder, tile_index)

        label = f"[{i + 1}/{len(ref_files)}] {ref_name}"
        if input_tile is None:
            print(f"{label}: SKIP (no matching input tile)")
            continue

        stats = verify_tile(input_tile, ref_path, tile_index, args.tolerance)
        if stats["status"] == "skip":
            print(f"{label}: SKIP ({stats['reason']})")
            continue

        status_str = "PASS" if stats["status"] == "pass" else "FAIL"
        print(
            f"{label}: {status_str}  "
            f"max_err={stats['max_error']:.4f}  "
            f"mean_err={stats['mean_error']:.6f}  "
            f"exact={stats['exact_match_pct']:.1f}%  "
            f"within_tol={stats['within_tolerance_pct']:.1f}%  "
            f"cells={stats['total_cells']}  "
            f"nodata={stats['nodata_cells']}"
        )
        if stats["status"] != "pass":
            all_pass = False

    print()
    if all_pass:
        print("All tiles PASSED.")
    else:
        print("Some tiles FAILED.")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
