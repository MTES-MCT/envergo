import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from bulk_carto_creation import bulk_carto_creation
from create_carto import bassinVersantParameters, create_carto
from matplotlib.colors import ListedColormap
from utils.carto import (
    create_quadrants,
    get_carto_info,
    load_carto,
    save_array_to_carto,
)
from utils.carto_querier import cartoQuerier

ALTI_PARENT_FOLDER = str(Path(__file__).parent)


def test_plot():
    q_nb = 8
    radii = [50, 75, 100, 130, 160]
    inner_atli, quads, _ = create_quadrants(
        x=1155,
        y=1650,
        carto_precision=5,
        inner_radius=25,
        radii=radii,
        quadrants_nb=q_nb,
    )
    for i in range(4):
        print(i, quads[i])
    plot_quadrants(inner_atli, quads, radii, q_nb)


def plot_quadrants(inner_atli, quads, radii, q_nb):
    colors = ["blue", "purple", "red", "pink", "orange", "yellow", "lime", "green"]
    fig, ax = plt.subplots()
    ax.set_xlim([0, 1000])
    ax.set_ylim([0, 1000])
    ax.scatter(
        [p[0] for p in inner_atli], [p[1] for p in inner_atli], color="grey", s=0.1
    )
    for q in range(q_nb):
        for i, _ in enumerate(radii):
            ax.scatter(
                [1000 - p[1] / 5 for p in quads[q][i]],
                [p[0] / 5 for p in quads[q][i]],
                color=colors[q],
                s=(i + 1) ** 2,
            )

    plt.show()


def plot_alti_carto(
    alti_carto_file,
    title,
    alpha=1,
    stretch=1,
    given_ax=None,
    colormap=None,
    vmin=None,
    vmax=None,
):
    if given_ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(111)
    else:
        ax = given_ax

    h = load_carto(alti_carto_file)
    h = np.repeat(np.repeat(h, stretch, axis=0), stretch, axis=1)
    ax.set_title(title)

    if colormap == "bassin_versant":
        cmap = mpl.colors.ListedColormap(["white", "orange", "red"])
        my_cmap = cmap(np.arange(cmap.n))
        my_cmap[:, -1] = [0, 1, 0.7]
        my_cmap = mpl.colors.ListedColormap(my_cmap)
        bounds = [0, 3000, 8000, 80000]
        norm = mpl.colors.boundary_norm(bounds, cmap.n)
        plt.imshow(h, alpha=alpha, cmap=my_cmap, norm=norm)
        cbar = plt.colorbar()
        cbar.ax.set_ylabel("surface de bassin versant en m2", rotation=270)

    elif colormap == "alti":
        plt.imshow(
            h,
            alpha=alpha,
            cmap=ListedColormap(
                mpl.colormaps["gist_earth"](np.linspace(0.25, 0.85, 155))
            ),
        )
        cbar = plt.colorbar()
        cbar.ax.set_ylabel("altitude en m", rotation=270)

    elif colormap == "decision":
        cmap = mpl.colors.ListedColormap(
            [
                "black",
                "red",
                "orange",
                "white",
                "pink",
                "purple",
                "black",
            ]
        )
        my_cmap = cmap(np.arange(cmap.n))
        # my_cmap[:,-1] = [0,1,0.7]
        my_cmap = mpl.colors.ListedColormap(my_cmap)
        bounds = [-9.5, -8, -2, -0.5, 0.5, 2, 9.5, 10]
        norm = mpl.colors.boundary_norm(bounds, cmap.n)
        plt.imshow(h, alpha=alpha, cmap=my_cmap, norm=norm)
        cbar = plt.colorbar()

    elif colormap:
        plt.imshow(h, alpha=alpha, cmap=mpl.colormaps[colormap], vmin=vmin, vmax=vmax)
        plt.colorbar()

    else:
        plt.imshow(h, alpha=alpha)
        plt.colorbar()

    return ax


def test_carto_creator(
    params,
    current_tile,
    output_carto_precision,
    ouptut_file,
    ouptut_screen_shot,
    input_folder,
    show=False,
):
    create_carto(
        params,
        current_tile,
        output_carto_precision,
        ouptut_file,
        input_folder,
    )
    carte = current_tile
    bassin_versant_plot(carte, ouptut_file, ouptut_screen_shot, show=show)


def bassin_versant_plot(
    alti_file,
    bassin_versant_file,
    save_png,
    title="bassin versant \n1 unité = 5m",
    show=True,
):
    bassin_versant_file_info = get_carto_info(bassin_versant_file)
    alti_file_info = get_carto_info(alti_file)
    ax = plot_alti_carto(
        alti_file, title, colormap="alti", stretch=round(1000 / alti_file_info["nrows"])
    )
    ax = plot_alti_carto(
        bassin_versant_file,
        title,
        alpha=0.5,
        stretch=round(1000 / bassin_versant_file_info["nrows"]),
        colormap="bassin_versant",
        given_ax=ax,
    )
    plt.savefig(save_png, dpi=500)
    if show:
        plt.show()


def compare_cartos(carto1, carto2, stretch=(1, 1)):
    c1 = np.repeat(
        np.repeat(load_carto(carto1), stretch[0], axis=0), stretch[0], axis=1
    )
    c2 = np.repeat(
        np.repeat(load_carto(carto2), stretch[1], axis=0), stretch[1], axis=1
    )
    car_name1 = carto1.split("/")[-1].split(".")[0]
    car_name2 = carto2.split("/")[-1].split(".")[0]
    diff = c1 - c2
    print("\n ====== comparaison : " + car_name1 + " et  " + car_name2 + " ======")
    print("stats c1 : moyenne : ", np.mean(c1), "ecart type : ", np.std(c1))
    print("stats c2 : moyenne : ", np.mean(c2), "ecart type : ", np.std(c2))
    print("abs diff moyenne :", np.mean(np.abs(diff)), "\n")
    save_array_to_carto(
        diff,
        ALTI_PARENT_FOLDER
        + "/output/diff/diff_"
        + car_name1
        + "_"
        + car_name2
        + ".asc",
        get_carto_info(carto1),
    )
    plot_alti_carto(
        ALTI_PARENT_FOLDER
        + "/output/diff/diff_"
        + car_name1
        + "_"
        + car_name2
        + ".asc",
        title="pourcentage de différence : " + car_name1 + " et  " + car_name2,
        alpha=1,
        colormap="cool",
        vmin=-10000,
        vmax=10000,
    )
    plt.savefig(
        ALTI_PARENT_FOLDER
        + "/output/diff/diff_"
        + car_name1
        + "_"
        + car_name2
        + ".png",
        dpi=500,
    )

    plt.show()


def compare_cartos_v2(
    carto1, carto2, barre1, barre2, stretch=(1, 1), interactive=False, save_dir=None
):
    def transform_array(arr):
        # create an array of zeros with the same shape as input
        result = np.zeros_like(arr)

        # apply the transformation function element-wise
        result[np.logical_and(arr > barre1, arr < barre2)] = 1
        result[arr >= barre2] = 10

        return result

    c1 = np.repeat(
        np.repeat(load_carto(carto1), stretch[0], axis=0), stretch[0], axis=1
    )
    c2 = np.repeat(
        np.repeat(load_carto(carto2), stretch[1], axis=0), stretch[1], axis=1
    )

    car_name1 = carto1.split("/")[-1].split(".")[0]
    car_name2 = carto2.split("/")[-1].split(".")[0]

    diff_category = transform_array(c2) - transform_array(c1)
    diff = c1 - c2
    changes = np.where(diff_category == 0, 0, diff)
    if save_dir is None:
        save_dir = (
            ALTI_PARENT_FOLDER
            + "/output/decision/"
            + car_name1
            + "_"
            + car_name2
            + "_proj_"
            + str(10000 - barre2)
        )
    if not Path(save_dir).exists():
        os.makedirs(save_dir)

    text_result = ""
    text_result += (
        "\n ====== comparaison : " + car_name1 + " et  " + car_name2 + " ======" + "\n"
    )
    text_result += (
        "stats c1 : moyenne : "
        + str(np.mean(c1))
        + "ecart type : "
        + str(np.std(c1))
        + "\n"
    )
    text_result += (
        "stats c2 : moyenne : "
        + str(np.mean(c2))
        + "ecart type : "
        + str(np.std(c2))
        + "\n"
    )
    text_result += "abs diff moyenne :" + str(np.mean(np.abs(diff))) + "\n"
    text_result += (
        "abs diff category moyenne :"
        + str(np.mean(np.abs(diff_category)))
        + "\n"
        + "\n"
    )

    if interactive:
        print(text_result)
    with open(save_dir + "/" + "stats_diff.txt", "w") as f:
        f.write(text_result)

    plt.clf()
    # plot the normal diff
    file = save_dir + "/" + "diff"
    save_array_to_carto(diff, file + ".asc", get_carto_info(carto1))
    plot_alti_carto(
        file + ".asc",
        title="différence absolue :\n" + car_name1 + "\n et \n" + car_name2,
        alpha=1,
        colormap="rd_bu",
        vmax=3000,
        vmin=-3000,
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    # plot the percentage diff
    file = save_dir + "/" + "diff_percentage"
    save_array_to_carto(diff / c1, file + ".asc", get_carto_info(carto1))
    plot_alti_carto(
        file + ".asc",
        title="différence pourcentage :\n" + car_name1 + "\n et \n" + car_name2,
        alpha=1,
        colormap="rd_bu",
        vmax=0.50,
        vmin=-0.50,
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    # plot the decision diff
    file = save_dir + "/" + "decision_diff"
    save_array_to_carto(diff_category, file + ".asc", get_carto_info(carto1))
    plot_alti_carto(
        file + ".asc",
        title="différence de décision :\n" + car_name1 + "\n et \n" + car_name2,
        alpha=1,
        colormap="decision",
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    # plot the diff when the decision was changed
    file = save_dir + "/" + "decision__changes_diff"
    save_array_to_carto(changes, file + ".asc", get_carto_info(carto1))
    plot_alti_carto(
        file + ".asc",
        title="valeur de la différence menant à un changement de catégorie\npour: "
        + car_name1
        + "\n et \n"
        + car_name2,
        alpha=1,
        colormap="rd_bu",
        vmax=3000,
        vmin=-3000,
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    unique_values, value_counts = np.unique(diff_category, return_counts=True)
    non_zero_values = unique_values[unique_values != 0]
    non_zero_counts = value_counts[unique_values != 0] / (
        diff_category.shape[0] * diff_category.shape[1]
    )
    plt.bar(non_zero_values, non_zero_counts)
    plt.title(
        "répartition des changements de catégorie\npour: "
        + car_name1
        + "\n et \n"
        + car_name2
    )
    plt.savefig(
        save_dir + "/" + "decision__changes_rep" + ".png", dpi=500, bbox_inches="tight"
    )
    plt.clf()

    if interactive:
        plt.show()


def run_tests():
    compare_cartos_go = False
    if compare_cartos_go:
        test_dir = ALTI_PARENT_FOLDER + "/output/test/"

        compare_cartos_v2(
            test_dir + "test_20_20_8.asc",
            test_dir + "test_20_5_12.asc",
            5000,
            8000,
            stretch=(1, 1),
        )
        compare_cartos_v2(
            test_dir + "test_20_10_12.asc",
            test_dir + "test_20_5_12.asc",
            5000,
            8000,
            stretch=(1, 1),
        )

    generate_one_carto = False
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
            current_tile=ALTI_PARENT_FOLDER
            + "/alti_data/rgealti_fxx_0285_6710_mnt_lamb93_ign69.asc",
            output_carto_precision=20,
            ouptut_file=ALTI_PARENT_FOLDER + "/output/test/" + name + ".asc",
            ouptut_screen_shot=ALTI_PARENT_FOLDER + "/output/test/" + name + ".png",
            input_folder=ALTI_PARENT_FOLDER + "/alti_data",
            show=True,
        )

    test_big_carto = False
    if test_big_carto:
        cqot = cartoQuerier(
            ALTI_PARENT_FOLDER + "/alti_data",
            ALTI_PARENT_FOLDER
            + "/alti_data/rgealti_fxx_0285_6710_mnt_lamb93_ign69.asc",
        )
        save_array_to_carto(
            cqot.current_big_carto,
            ALTI_PARENT_FOLDER + "/output/big_carto.asc",
            {
                "ncols": 3000,
                "nrows": 3000,
                "xllcorner": 285000,
                "yllcorner": 675000,
                "cellsize": 5,
                "nodata_value": -99999.00,
            },
        )
        plot_alti_carto(ALTI_PARENT_FOLDER + "/output/big_carto.asc", "big_carto")
        plt.show()

    create_bulk_carto = False
    if create_bulk_carto:
        bulk_carto_creation(
            ALTI_PARENT_FOLDER + "/alti_data", ALTI_PARENT_FOLDER + "/output/bulk_bv"
        )


run_tests()
