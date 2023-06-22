import os
from datetime import datetime
from pathlib import Path

from create_carto import bassinVersantParameters
from utils import carto
from visualization import compare_cartos_v2, test_carto_creator

ALTI_PARENT_FOLDER = str(Path(__file__).parent)


def benchmark_parameters(
    params_to_benchmark,
    comparisons_to_do,
    places_to_evaluate,
    project_surface=2000,
    benchmark_folder=None,
):
    def get_name(place, params: bassinVersantParameters):
        bottom_left = carto.get_bottom_left_corner(place[1])
        return (
            f"{place[0]}_{bottom_left[0]}_{bottom_left[1]}__test_20_"
            + f"{params.carto_precision}_{params.quadrants_nb}_{params.slope}"
            + "-".join([str(r) for r in params.radii])
        )

    def get_data_folder(carto_file_name):
        return "/".join(carto_file_name.split("/")[:-1])

    if benchmark_folder is None:
        now = datetime.now()
        benchmark_folder = f"{ALTI_PARENT_FOLDER}/output/benchmarks/{now.strftime('%Y_%m_%d_%H_%M_%S')}"
        os.mkdirs(f"{benchmark_folder}/cartos")

        for place in places_to_evaluate:
            for params in params_to_benchmark:
                print("doing : ", place, params, "\n")
                name = get_name(place, params)
                ouput_id = f"{benchmark_folder}/cartos/{name}"
                test_carto_creator(
                    params,
                    current_tile=place[1],
                    output_carto_precision=20,
                    ouptut_file=f"{ouput_id}.asc",
                    ouptut_screen_shot=f"{ouput_id}.png",
                    input_folder=get_data_folder(place[1]),
                    show=False,
                )

    for place in places_to_evaluate:
        for params1, params2 in comparisons_to_do:
            print("evaluating : ", place, params1, params2)
            os.mkdirs(f"{benchmark_folder}/graphs")
            save_dir = (
                f"{benchmark_folder}/graphs/{place[0]}_"
                + f"{str(carto.get_bottom_left_corner(place[1])[0])}_"
                + f"{carto.get_bottom_left_corner(place[1])[1]}/"
                + f"{params1.carto_precision}v{params2.carto_precision}_"
                + f"{'-'.join([str(p) for p in params1.radii])}v{'-'.join([str(p) for p in params2.radii])}_"
                + f"{params1.quadrants_nb}v{params2.quadrants_nb}"
            )
            compare_cartos_v2(
                f"{benchmark_folder}/cartos/{get_name(place, params2)}.asc",
                f"{benchmark_folder}/cartos/{get_name(place, params1)}.asc",
                7000 - project_surface,
                10000 - project_surface,
                stretch=(1, 1),
                save_dir=save_dir,
            )


rayons2 = [50, 75, 100, 130, 160]
rayons1 = [50, 70, 90, 110, 130, 145, 160]
rayons0 = [59, 81, 98, 113, 126, 138, 149, 160]
rayons00 = [55, 74, 89, 102, 113, 123, 133, 142, 150, 158]

p1_12 = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=rayons1,
    quadrants_nb=12,
    slope=0.025,
)
p1_16 = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=rayons1,
    quadrants_nb=16,
    slope=0.025,
)
p0_12 = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=rayons0,
    quadrants_nb=12,
    slope=0.025,
)
p0_16 = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=rayons0,
    quadrants_nb=16,
    slope=0.025,
)
p00_12 = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=rayons00,
    quadrants_nb=12,
    slope=0.025,
)
p00_16 = bassinVersantParameters(
    carto_precision=5,
    inner_radius=25,
    radii=rayons00,
    quadrants_nb=16,
    slope=0.025,
)

params_to_benchmark = [p1_12, p0_12, p00_12, p1_16, p0_16, p00_16]

f = (p1_16, p1_12)
g = (p0_12, p1_12)
h = (p0_16, p1_16)
i = (p0_16, p0_12)
j = (p00_12, p0_12)
k = (p00_16, p0_16)


comparisons_to_do = [f, g, h, i, j, k]

places_to_evaluate = [
    [
        "44",
        f"{ALTI_PARENT_FOLDER}alti_data/rgealti_fxx_0285_6710_mnt_lamb93_ign69.asc",
    ],
    [
        "39",
        f"{ALTI_PARENT_FOLDER}alti_data_39/rgealti_fxx_0890_6625_mnt_lamb93_ign69.asc",
    ],
    [
        "29",
        f"{ALTI_PARENT_FOLDER}alti_data_29/rgealti_fxx_0215_6845_mnt_lamb93_ign69.asc",
    ],
]

project_surface = 2000

benchmark_parameters(
    params_to_benchmark,
    comparisons_to_do,
    places_to_evaluate,
    project_surface,
    generate_cartos=True,
)
