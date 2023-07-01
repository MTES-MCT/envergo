import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from create_carto import create_carto
from matplotlib.colors import ListedColormap
from utils.bassin_versant_show import get_bassin_versant_sections_one_point
from utils.carto import (
    create_quadrants,
    get_carto_info,
    load_carto,
    save_array_to_carto,
    update_origin,
)
from utils.carto_querier import cartoQuerier

ALTI_PARENT_FOLDER = str(Path(__file__).parent)


def test_plot():
    """
    Test de l'affichage de quadrants.
    """
    q_nb = 8
    radii = [50, 75, 100, 130, 160]
    inner_atli, quads = create_quadrants(
        carto_precision=5,
        inner_radius=25,
        radii=radii,
        quadrants_nb=q_nb,
    )
    for i in range(4):
        print(i, quads[i])
    plot_quadrants(inner_atli, quads, radii, q_nb)


def plot_quadrants(inner_atli, quads, radii, q_nb):
    """
    Test de l 'affichage de quadrants paramétrable.

    Args:
        inner_atli (List[Tuple[int, int]]): Liste des coordonnées x, y de l'atli interne.
        quads (List[List[List[Tuple[int, int]]]]): Liste des quadrants.
        radii (List[int]): Liste des rayons.
        q_nb (int): Nombre de quadrants.
    """
    colors = [
        "#ff0000",
        "#ff8000",
        "#ffff00",
        "#80ff00",
        "#00ff00",
        "#00ff80",
        "#00ffff",
        "#0080ff",
        "#0000ff",
        "#8000ff",
        "#ff00ff",
        "#ff0080",
    ]
    fig, ax = plt.subplots()
    ax.scatter(
        [p[1] for p in inner_atli], [p[0] for p in inner_atli], color="grey", s=0.1
    )
    for q in range(q_nb):
        for i, _ in enumerate(radii):
            ax.scatter(
                [p[1] for p in quads[q][i]],
                [p[0] for p in quads[q][i]],
                color=colors[q],
                s=5 + 10 * (1 - i % 2),
            )

    plt.show()


def plot_carto(
    carto_file,
    title,
    alpha=1,
    stretch=1,
    given_ax=None,
    colormap=None,
    vmin=None,
    vmax=None,
    colorbar=True,
):
    """
    Affiche une carto.

    Args:
        carto_file (str): Chemin du fichier de la carto.
        title (str): Titre du graphique.
        alpha (float, optional): Valeur d'opacité. Par défaut 1.
        stretch (int, optional): Facteur d'étirement. Par défaut 1.
        given_ax (Axes, optional): Axes donné. Par défaut None.
            Si donné, le plot s'effectuera par dessus celui déjà présent.
        colormap (str, optional): Nom de la colormap. Par défaut None.
        vmin (float, optional): Valeur minimale de l'échelle de couleur. Par défaut None.
        vmax (float, optional): Valeur maximale. Par défaut None.
    """
    if given_ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(111)
    else:
        ax = given_ax

    h = load_carto(carto_file)
    h = np.repeat(np.repeat(h, stretch, axis=0), stretch, axis=1)
    ax.set_title(title)

    if colormap == "bassin_versant":
        cmap = mpl.colors.ListedColormap(["white", "orange", "red"])
        my_cmap = cmap(np.arange(cmap.N))
        my_cmap[:, -1] = [0, 1, 0.7]
        my_cmap = mpl.colors.ListedColormap(my_cmap)
        bounds = [0, 5000, 8000, 80000]
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
        plt.imshow(h, alpha=alpha, cmap=my_cmap, norm=norm)
        if colorbar:
            cbar = plt.colorbar()
            cbar.ax.set_ylabel(
                "surface de bassin versant en m2", rotation=270, labelpad=5
            )

    elif colormap == "alti":
        plt.imshow(
            h,
            alpha=alpha,
            cmap=ListedColormap(
                mpl.colormaps["gist_earth"](np.linspace(0.25, 0.85, 155))
            ),
        )
        if colorbar:
            cbar = plt.colorbar()
            cbar.ax.set_ylabel("altitude en m", rotation=270, labelpad=5)

    elif colormap == "decision":
        cmap = mpl.colors.ListedColormap(
            [
                "red",
                "orange",
                "yellow",
                (0, 0, 0, 0),
                "blue",
                "green",
                "black",
            ]
        )
        my_cmap = cmap(np.arange(cmap.N))
        # my_cmap[:,-1] = [0,1,0.7]
        my_cmap = mpl.colors.ListedColormap(my_cmap)
        bounds = [-10, -9.5, -2, -0.5, 0.5, 2, 9.5, 10]
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
        plt.imshow(h, alpha=alpha, cmap=my_cmap, norm=norm)
        if colorbar:
            cbar = plt.colorbar()

    elif colormap:
        plt.imshow(h, alpha=alpha, cmap=mpl.colormaps[colormap], vmin=vmin, vmax=vmax)
        if colorbar:
            plt.colorbar()

    else:
        plt.imshow(h, alpha=alpha)
        if colorbar:
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


def plot_sections_point_bassin_versant(
    paramsList,
    input_folder,
    current_tile,
    comparison,
    point,
    disp,
):
    decision_diff_tile = f"{comparison}/decision_diff.asc"
    carto_machine = cartoQuerier(input_folder, current_tile)
    alti_file_info = get_carto_info(current_tile)
    decision_diff_file_info = get_carto_info(decision_diff_tile)

    def fit_to_tile(points):
        new_x = np.round(
            (points[:, 0] - alti_file_info["x_range"][0]) / alti_file_info["cellsize"]
        )
        new_y = (
            np.round(
                alti_file_info["nrows"]
                - (points[:, 1] - alti_file_info["y_range"][0])
                / alti_file_info["cellsize"]
            )
            - 1
        )
        return np.column_stack((new_y, new_x))

    title = f"Bassin versant sections for {point}\n" + "\n".join(
        [f"{paramIndex}:{params.radii}" for paramIndex, params in enumerate(paramsList)]
    )

    ax = plot_carto(
        current_tile,
        title,
        colormap="alti",
        stretch=round(1000 / alti_file_info["nrows"]),
    )
    ax = plot_carto(
        decision_diff_tile,
        title,
        colormap="decision",
        stretch=round(1000 / decision_diff_file_info["nrows"]),
        alpha=0.2,
        given_ax=ax,
    )
    ax = plot_carto(
        current_tile,
        title,
        colormap="alti",
        stretch=round(1000 / alti_file_info["nrows"]),
        given_ax=ax,
        alpha=0,
        colorbar=False,
    )

    point = (
        round(
            alti_file_info["x_range"][0]
            + point[1]
            * alti_file_info["cellsize"]
            * alti_file_info["nrows"]
            / decision_diff_file_info["nrows"]
        ),
        round(
            alti_file_info["y_range"][1]
            - (point[0] * alti_file_info["cellsize"])
            * alti_file_info["nrows"]
            / decision_diff_file_info["nrows"]
            - 15
        ),
    )

    [p] = fit_to_tile(np.array([np.array([point[0], point[1]])]))
    ax.scatter(
        [p[1]],
        [p[0]],
        color="black",
    )
    c = plt.Circle(
        (p[1], p[0]),
        paramsList[0].inner_radius / alti_file_info["cellsize"],
        color="black",
        fill=False,
        alpha=0.3,
    )
    ax.add_patch(c)

    for paramIndex, params in enumerate(paramsList):
        (
            origin_less_inner_circle_points,
            origin_less_quadrants_points,
        ) = create_quadrants(
            params.carto_precision,
            params.inner_radius,
            params.radii,
            params.quadrants_nb,
        )
        if carto_machine.query_one_point(point) is not None:
            inner_circle_points = update_origin(point, origin_less_inner_circle_points)

            quadrants = []
            for q in range(params.quadrants_nb):
                quadrants.append([])
                for i, _ in enumerate(params.radii):
                    quadrants[q].append([])
                    quadrants[q][i] = carto_machine.get_mean_alti(
                        update_origin(point, origin_less_quadrants_points[q][i])
                    )

            inner_circle_alti = carto_machine.get_mean_alti(inner_circle_points)
            bassin_versant_sections = get_bassin_versant_sections_one_point(
                inner_circle_alti,
                quadrants,
                params.inner_radius,
                params.radii,
                params.slope,
            )

            normalized_inner_circle_points = fit_to_tile(inner_circle_points)
            ax.scatter(
                [p[1] for p in normalized_inner_circle_points],
                [p[0] for p in normalized_inner_circle_points],
                color="black",
                s=0.1,
            )
            if any([any(quad) for quad in bassin_versant_sections]):
                ok_sections_points = np.concatenate(
                    [
                        fit_to_tile(
                            update_origin(point, origin_less_quadrants_points[q][i])
                        )
                        for i in range(len(params.radii))
                        for q in range(len(quadrants))
                        if bassin_versant_sections[q][i]
                    ]
                )

                ax.scatter(
                    [p[1] for p in ok_sections_points],
                    [p[0] for p in ok_sections_points],
                    color=disp[paramIndex][0],
                    s=5,
                    alpha=disp[paramIndex][1],
                    label=f"params nb : {paramIndex}, bv: {round(np.sum(bassin_versant_sections)/params.quadrants_nb)}",
                )
                ax.legend()

            for r in params.radii:
                c = plt.Circle(
                    (p[1], p[0]),
                    r / alti_file_info["cellsize"],
                    color=disp[paramIndex][0],
                    fill=False,
                    alpha=0.3,
                )
                ax.add_patch(c)

    plt.tight_layout()
    plt.show()


def bassin_versant_plot(
    alti_file,
    bassin_versant_file,
    save_png,
    title=None,
    show=True,
):
    if title is not None:
        title = f"{bassin_versant_file.split('/')[-1]}\nbassin versant \n1 unité = 5m"
    bassin_versant_file_info = get_carto_info(bassin_versant_file)
    alti_file_info = get_carto_info(alti_file)
    ax = plot_carto(
        alti_file, title, colormap="alti", stretch=round(1000 / alti_file_info["nrows"])
    )
    ax = plot_carto(
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
    print(f"\n ====== comparaison : {car_name1} et  {car_name2} ======")
    print(f"stats c1 : moyenne : {np.mean(c1)} | ecart type : {np.std(c1)}")
    print(f"stats c2 : moyenne : {np.mean(c2)} | ecart type : {np.std(c2)}")
    print(f"abs diff moyenne : {np.mean(np.abs(diff))}\n")
    ouput_name = (f"{ALTI_PARENT_FOLDER}/output/diff/diff_{car_name1}_{car_name2}",)
    save_array_to_carto(
        diff,
        f"{ouput_name}.asc",
        get_carto_info(carto1),
    )
    plot_carto(
        f"{ouput_name}.asc",
        title=f"pourcentage de différence : {car_name1} et  {car_name2}",
        alpha=1,
        colormap="cool",
        vmin=-10000,
        vmax=10000,
    )
    plt.savefig(
        f"{ouput_name}.png",
        dpi=500,
    )

    plt.show()


def compare_cartos_v2(
    carto1, carto2, barre1, barre2, stretch=(1, 1), interactive=False, save_dir=None
):
    """
    Compare deux représentations cartographiques (cartos) et génère des statistiques
    et des visualisations des différences.

    Arguments :
        - path_c1 (str) : Chemin vers le fichier de la première carto.
        - path_c2 (str) : Chemin vers le fichier de la deuxième carto.
        - barre1 (float) : Valeur de la première barre de seuil pour la catégorisation.
        - barre2 (float) : Valeur de la deuxième barre de seuil pour la catégorisation.
        - stretch (tuple) : Facteurs d'étirement pour ajuster les cartographies entre elles (défaut: (1, 1)).
        - save_dir (str) : Répertoire de sauvegarde des résultats (défaut: "output/decision/carto1_carto2_proj_proj-surface").
        - interactive (bool) : Indique si les résultats doivent être affichés de manière interactive (défaut: False).
    """

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
        save_dir = f"{ALTI_PARENT_FOLDER}/output/decision/{car_name1}_{car_name2}_proj_{10000 - barre2}"

    def get_stats():
        if not Path(save_dir).exists():
            os.makedirs(save_dir)

        text_result = ""
        text_result += f"\n ====== comparaison : {car_name1} et {car_name2} ======\n"
        text_result += (
            f"stats c1 : moyenne : {np.mean(c1)} | ecart type : {np.std(c1)}\n"
        )

        text_result += (
            f"stats c1 : moyenne : {np.mean(c2)} | ecart type : {np.std(c2)}\n"
        )

        text_result += f"abs diff moyenne : {np.mean(np.abs(diff))}\n"
        text_result += (
            f"abs diff category moyenne : {np.mean(np.abs(diff_category))}\n\n"
        )

        if interactive:
            print(text_result)
        with open(f"{save_dir}/stats_diff.txt", "w") as f:
            f.write(text_result)

    def get_intersting_points():
        text_result = ""
        text_result += (
            f"\n ====== interesting points : {car_name1} et {car_name2} ======\n"
        )
        for value in [10, 9, 1, -1, -9, -10]:
            interesting_points = np.where(diff_category == value)
            text_result += f"points {value} : \n"
            text_result += (
                ", ".join(
                    [
                        f"({interesting_points[0][i]},{interesting_points[1][i]})"
                        for i in range(len(interesting_points[0]))
                    ]
                )
                + "\n"
            )

        if interactive:
            print(text_result)
        with open(f"{save_dir}/interesting_points.txt", "w") as f:
            f.write(text_result)

    def plot_diff():
        plt.clf()
        # plot the normal diff
        file = f"{save_dir}/diff"
        save_array_to_carto(diff, f"{file}.asc", get_carto_info(carto1))
        plot_carto(
            f"{file}.asc",
            title=f"différence absolue :\n{car_name1}\n et \n{car_name2}",
            alpha=1,
            colormap="RdBu",
            vmax=3000,
            vmin=-3000,
        )
        plt.savefig(f"{file}.png", dpi=500, bbox_inches="tight")

    def plot_diff_percentage():
        plt.clf()
        # plot the percentage diff
        file = f"{save_dir}/diff_percentage"
        save_array_to_carto(diff / c1, f"{file}.asc", get_carto_info(carto1))
        plot_carto(
            f"{file}.asc",
            title=f"différence pourcentage :\n{car_name1}\n et \n{car_name2}",
            alpha=1,
            colormap="RdBu",
            vmax=0.50,
            vmin=-0.50,
        )
        plt.savefig(f"{file}.png", dpi=500, bbox_inches="tight")

    def plot_decision_diff():
        plt.clf()

        # plot the decision diff
        file = f"{save_dir}/decision_diff"
        save_array_to_carto(diff_category, f"{file}.asc", get_carto_info(carto1))
        plot_carto(
            f"{file}.asc",
            title=f"différence de décision :\n{car_name1} \n et \n{car_name2}",
            alpha=1,
            colormap="decision",
        )
        plt.savefig(f"{file}.png", dpi=500, bbox_inches="tight")

    def plot_diff_changes():
        plt.clf()

        # plot the diff when the decision was changed
        file = f"{save_dir}/decision_changes_diff"
        save_array_to_carto(changes, f"{file}.asc", get_carto_info(carto1))
        plot_carto(
            f"{file}.asc",
            title="valeur de la différence menant à un changement de catégorie\npour: "
            + f"{car_name1}\n et \n{car_name2}",
            alpha=1,
            colormap="RdBu",
            vmax=3000,
            vmin=-3000,
        )
        plt.savefig(f"{file}.png", dpi=500, bbox_inches="tight")

    def plot_diff_changes_rep():
        plt.clf()

        unique_values, value_counts = np.unique(diff_category, return_counts=True)
        non_zero_values = unique_values[unique_values != 0]
        non_zero_counts = value_counts[unique_values != 0] / (
            diff_category.shape[0] * diff_category.shape[1]
        )
        plt.bar(non_zero_values, non_zero_counts)
        plt.title(
            "répartition des changements de catégorie\npour: "
            + f"{car_name1}\n et \n{car_name2}"
        )
        plt.savefig(
            f"{save_dir}/decision_diff_changes_rep.png", dpi=500, bbox_inches="tight"
        )

        if interactive:
            plt.show()

    get_stats()
    get_intersting_points()
    plot_diff()
    plot_diff_percentage()
    plot_decision_diff()
    plot_diff_changes()
    plot_diff_changes_rep()
