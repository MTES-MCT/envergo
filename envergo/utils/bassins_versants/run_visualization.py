from pathlib import Path

import matplotlib.pyplot as plt
from create_carto import bassinVersantParameters
from mass_carto_creation import mass_carto_creation
from utils.carto import create_quadrants, save_array_to_carto
from utils.carto_querier import cartoQuerier
from visualization import (
    compare_cartos_v2,
    plot_carto,
    plot_quadrants,
    plot_sections_point_bassin_versant,
    test_carto_creator,
)

ALTI_PARENT_FOLDER = str(Path(__file__).parent)


def run_tests(
    plot_quadrants_go=False,
    plot_bassin_versant_sections=False,
    compare_cartos_go=False,
    generate_one_carto=False,
    test_big_carto=False,
    create_mass_carto=False,
):
    """
    Lance les tests de visualisation en fonction des variables qui sont passées à True

    Args:
        plot_quadrants (bool): Indique si les tests d'affichage de quadrants doivent être lancés.
        plot_bassin_versant_sections (bool): Indique si les tests d'affichage de section correspondant au bassin versant doivent être lancés.
        compare_cartos_go (bool): Indique si les tests de comparaison de cartos doivent être lancés.
        generate_one_carto (bool): Indique si le test de génération d'une seule carto doit être lancé.
        test_big_carto (bool): Indique si le test de visualisation de la "big carto" doit être lancé.
        create_mass_carto (bool): Indique si le test de création massive de carto doit être lancé.
    """
    if plot_quadrants_go:
        q_nb = 12
        radii = [59, 81, 98, 113, 126, 138, 149, 160]
        inner_atli, quads = create_quadrants(
            carto_precision=5,
            inner_radius=25,
            radii=radii,
            quadrants_nb=q_nb,
        )

        plot_quadrants(inner_atli, quads, radii, q_nb)

    if plot_bassin_versant_sections:
        rayons0 = [59, 81, 98, 113, 126, 138, 149, 160]
        rayons1 = [50, 70, 90, 110, 130, 145, 160]
        p0_12 = bassinVersantParameters(
            carto_precision=5,
            inner_radius=25,
            radii=rayons0,
            quadrants_nb=12,
            slope=0.05,
        )
        p1_12 = bassinVersantParameters(
            carto_precision=5,
            inner_radius=25,
            radii=rayons1,
            quadrants_nb=12,
            slope=0.05,
        )
        # replace this info with the point, params comparison and alti tile you want to study
        point = (56, 196)
        input_folder = f"{ALTI_PARENT_FOLDER}/alti_data_39"
        alti_tile = f"{input_folder}/rgealti_fxx_0890_6625_mnt_lamb93_ign69.asc"
        comparison = f"{ALTI_PARENT_FOLDER}/output/benchmarks/2023_07_02_09_38_27/decision/39_890000_6620000/5v5_r0vr1_12v12"
        disp = [("blue", 0.5), ("red", 0.3)]
        params = [p0_12, p1_12]

        plot_sections_point_bassin_versant(
            params, input_folder, alti_tile, comparison, point, disp
        )

    if compare_cartos_go:
        test_dir = f"{ALTI_PARENT_FOLDER}output/test/"

        compare_cartos_v2(
            f"{test_dir}test_20_20_8.asc",
            f"{test_dir}test_20_5_12.asc",
            5000,
            8000,
            stretch=(1, 1),
        )
        compare_cartos_v2(
            f"{test_dir}test_20_10_12.asc",
            f"{test_dir}test_20_5_12.asc",
            5000,
            8000,
            stretch=(1, 1),
        )

    if generate_one_carto:
        name = "test_20_5_12"
        params = bassinVersantParameters(
            carto_precision=5,
            inner_radius=25,
            radii=[50, 75, 100, 130, 160],
            quadrants_nb=12,
            slope=0.05,
        )
        test_carto_creator(
            params,
            current_tile=f"{ALTI_PARENT_FOLDER}/alti_data/rgealti_fxx_0285_6710_mnt_lamb93_ign69.asc",
            output_carto_precision=20,
            ouptut_file=f"{ALTI_PARENT_FOLDER}/output/test/{name}.asc",
            ouptut_screen_shot=f"{ALTI_PARENT_FOLDER}/output/test/{name}.png",
            input_folder=f"{ALTI_PARENT_FOLDER}/alti_data",
            show=True,
        )

    if test_big_carto:
        cqot = cartoQuerier(
            f"{ALTI_PARENT_FOLDER}/alti_data",
            f"{ALTI_PARENT_FOLDER}/alti_data/rgealti_fxx_0285_6710_mnt_lamb93_ign69.asc",
        )
        save_array_to_carto(
            cqot.current_big_carto,
            f"{ALTI_PARENT_FOLDER}/output/big_carto.asc",
            {
                "ncols": 3000,
                "nrows": 3000,
                "xllcorner": 285000,
                "yllcorner": 675000,
                "cellsize": 5,
                "nodata_value": -99999.00,
            },
        )
        plot_carto(f"{ALTI_PARENT_FOLDER}/output/big_carto.asc", "big_carto")
        plt.show()

    if create_mass_carto:
        mass_carto_creation(
            f"{ALTI_PARENT_FOLDER}alti_data", f"{ALTI_PARENT_FOLDER}output/mass_bv"
        )


run_tests(
    plot_quadrants_go=False,
    plot_bassin_versant_sections=True,
    compare_cartos_go=False,
    generate_one_carto=False,
    test_big_carto=False,
    create_mass_carto=False,
)
