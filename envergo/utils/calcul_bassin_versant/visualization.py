import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from bulk_carto_creation import bulkCartoCreation
from create_carto import createCarto
from matplotlib.colors import ListedColormap
from utils.carto import createQuadrants, getCartoInfo, loadCarto, saveArrayToCarto
from utils.cartoQuerier import cartoQuerier
from utils.classes import Parameters

ALTI_PARENT_FOLDER = str(Path(__file__).parent)


def testPlot():
    qNb = 8
    radii = [50, 75, 100, 130, 160]
    innerAtli, quads, _ = createQuadrants(
        x=1155, y=1650, cartoPrecision=5, innerRadius=25, radii=radii, quadrantsNb=qNb
    )
    for i in range(4):
        print(i, quads[i])
    plotQuadrants(innerAtli, quads, radii, qNb)


def plotQuadrants(innerAtli, quads, radii, qNb):
    colors = ["blue", "purple", "red", "pink", "orange", "yellow", "lime", "green"]
    fig, ax = plt.subplots()
    ax.set_xlim([0, 1000])
    ax.set_ylim([0, 1000])
    ax.scatter(
        [p[0] for p in innerAtli], [p[1] for p in innerAtli], color="grey", s=0.1
    )
    for q in range(qNb):
        for i, _ in enumerate(radii):
            ax.scatter(
                [1000 - p[1] / 5 for p in quads[q][i]],
                [p[0] / 5 for p in quads[q][i]],
                color=colors[q],
                s=(i + 1) ** 2,
            )

    plt.show()


def plotAltiCarto(
    altiCartoFile,
    title,
    alpha=1,
    stretch=1,
    givenAx=None,
    colormap=None,
    vmin=None,
    vmax=None,
):
    if givenAx is None:
        fig = plt.figure()
        ax = fig.add_subplot(111)
    else:
        ax = givenAx

    H = loadCarto(altiCartoFile)
    H = np.repeat(np.repeat(H, stretch, axis=0), stretch, axis=1)
    ax.set_title(title)

    if colormap == "bassinVersant":
        cmap = mpl.colors.ListedColormap(["white", "orange", "red"])
        my_cmap = cmap(np.arange(cmap.N))
        my_cmap[:, -1] = [0, 1, 0.7]
        my_cmap = mpl.colors.ListedColormap(my_cmap)
        bounds = [0, 3000, 8000, 80000]
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
        plt.imshow(H, alpha=alpha, cmap=my_cmap, norm=norm)
        cbar = plt.colorbar()
        cbar.ax.set_ylabel("surface de bassin versant en m2", rotation=270)

    elif colormap == "alti":
        plt.imshow(
            H,
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
        my_cmap = cmap(np.arange(cmap.N))
        # my_cmap[:,-1] = [0,1,0.7]
        my_cmap = mpl.colors.ListedColormap(my_cmap)
        bounds = [-9.5, -8, -2, -0.5, 0.5, 2, 9.5, 10]
        norm = mpl.colors.BoundaryNorm(bounds, cmap.N)
        plt.imshow(H, alpha=alpha, cmap=my_cmap, norm=norm)
        cbar = plt.colorbar()

    elif colormap:
        plt.imshow(H, alpha=alpha, cmap=mpl.colormaps[colormap], vmin=vmin, vmax=vmax)
        plt.colorbar()

    else:
        plt.imshow(H, alpha=alpha)
        plt.colorbar()

    return ax


def testCartoCreator(
    params,
    currentTile,
    outputCartoPrecision,
    ouptutFile,
    ouptutScreenShot,
    inputFolder,
    show=False,
):
    createCarto(
        params,
        currentTile,
        outputCartoPrecision,
        ouptutFile,
        inputFolder,
    )
    carte = currentTile
    bassinVersantPlot(carte, ouptutFile, ouptutScreenShot, show=show)


def bassinVersantPlot(
    altiFile,
    bassinVersantFile,
    savePng,
    title="Bassin versant \n1 unité = 5m",
    show=True,
):
    bassinVersantFileInfo = getCartoInfo(bassinVersantFile)
    altiFileInfo = getCartoInfo(altiFile)
    ax = plotAltiCarto(
        altiFile, title, colormap="alti", stretch=round(1000 / altiFileInfo["nrows"])
    )
    ax = plotAltiCarto(
        bassinVersantFile,
        title,
        alpha=0.5,
        stretch=round(1000 / bassinVersantFileInfo["nrows"]),
        colormap="bassinVersant",
        givenAx=ax,
    )
    plt.savefig(savePng, dpi=500)
    if show:
        plt.show()


def compareCartos(carto1, carto2, stretch=(1, 1)):
    c1 = np.repeat(np.repeat(loadCarto(carto1), stretch[0], axis=0), stretch[0], axis=1)
    c2 = np.repeat(np.repeat(loadCarto(carto2), stretch[1], axis=0), stretch[1], axis=1)
    carName1 = carto1.split("/")[-1].split(".")[0]
    carName2 = carto2.split("/")[-1].split(".")[0]
    diff = c1 - c2
    print("\n ====== Comparaison : " + carName1 + " et  " + carName2 + " ======")
    print("stats c1 : moyenne : ", np.mean(c1), "ecart type : ", np.std(c1))
    print("stats c2 : moyenne : ", np.mean(c2), "ecart type : ", np.std(c2))
    print("abs diff moyenne :", np.mean(np.abs(diff)), "\n")
    saveArrayToCarto(
        diff,
        ALTI_PARENT_FOLDER + "/output/diff/diff_" + carName1 + "_" + carName2 + ".asc",
        getCartoInfo(carto1),
    )
    plotAltiCarto(
        ALTI_PARENT_FOLDER + "/output/diff/diff_" + carName1 + "_" + carName2 + ".asc",
        title="Pourcentage de différence : " + carName1 + " et  " + carName2,
        alpha=1,
        colormap="cool",
        vmin=-10000,
        vmax=10000,
    )
    plt.savefig(
        ALTI_PARENT_FOLDER + "/output/diff/diff_" + carName1 + "_" + carName2 + ".png",
        dpi=500,
    )

    plt.show()


def compareCartosV2(
    carto1, carto2, barre1, barre2, stretch=(1, 1), interactive=False, saveDir=None
):
    def transform_array(arr):
        # Create an array of zeros with the same shape as input
        result = np.zeros_like(arr)

        # Apply the transformation function element-wise
        result[np.logical_and(arr > barre1, arr < barre2)] = 1
        result[arr >= barre2] = 10

        return result

    c1 = np.repeat(np.repeat(loadCarto(carto1), stretch[0], axis=0), stretch[0], axis=1)
    c2 = np.repeat(np.repeat(loadCarto(carto2), stretch[1], axis=0), stretch[1], axis=1)

    carName1 = carto1.split("/")[-1].split(".")[0]
    carName2 = carto2.split("/")[-1].split(".")[0]

    diffCategory = transform_array(c2) - transform_array(c1)
    diff = c1 - c2
    changes = np.where(diffCategory == 0, 0, diff)
    if saveDir is None:
        saveDir = (
            ALTI_PARENT_FOLDER
            + "/output/decision/"
            + carName1
            + "_"
            + carName2
            + "_proj_"
            + str(10000 - barre2)
        )
    if not Path(saveDir).exists():
        os.makedirs(saveDir)

    textResult = ""
    textResult += (
        "\n ====== Comparaison : " + carName1 + " et  " + carName2 + " ======" + "\n"
    )
    textResult += (
        "stats c1 : moyenne : "
        + str(np.mean(c1))
        + "ecart type : "
        + str(np.std(c1))
        + "\n"
    )
    textResult += (
        "stats c2 : moyenne : "
        + str(np.mean(c2))
        + "ecart type : "
        + str(np.std(c2))
        + "\n"
    )
    textResult += "abs diff moyenne :" + str(np.mean(np.abs(diff))) + "\n"
    textResult += (
        "abs diff category moyenne :" + str(np.mean(np.abs(diffCategory))) + "\n" + "\n"
    )

    if interactive:
        print(textResult)
    with open(saveDir + "/" + "stats_diff.txt", "w") as f:
        f.write(textResult)

    plt.clf()
    # Plot the normal diff
    file = saveDir + "/" + "diff"
    saveArrayToCarto(diff, file + ".asc", getCartoInfo(carto1))
    plotAltiCarto(
        file + ".asc",
        title="Différence absolue :\n" + carName1 + "\n et \n" + carName2,
        alpha=1,
        colormap="RdBu",
        vmax=3000,
        vmin=-3000,
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    # Plot the percentage diff
    file = saveDir + "/" + "diff_percentage"
    saveArrayToCarto(diff / c1, file + ".asc", getCartoInfo(carto1))
    plotAltiCarto(
        file + ".asc",
        title="Différence pourcentage :\n" + carName1 + "\n et \n" + carName2,
        alpha=1,
        colormap="RdBu",
        vmax=0.50,
        vmin=-0.50,
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    # Plot the decision diff
    file = saveDir + "/" + "decision_diff"
    saveArrayToCarto(diffCategory, file + ".asc", getCartoInfo(carto1))
    plotAltiCarto(
        file + ".asc",
        title="Différence de décision :\n" + carName1 + "\n et \n" + carName2,
        alpha=1,
        colormap="decision",
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    # Plot the diff when the decision was changed
    file = saveDir + "/" + "decision__changes_diff"
    saveArrayToCarto(changes, file + ".asc", getCartoInfo(carto1))
    plotAltiCarto(
        file + ".asc",
        title="Valeur de la différence menant à un changement de catégorie\npour: "
        + carName1
        + "\n et \n"
        + carName2,
        alpha=1,
        colormap="RdBu",
        vmax=3000,
        vmin=-3000,
    )
    plt.savefig(file + ".png", dpi=500, bbox_inches="tight")
    plt.clf()

    unique_values, value_counts = np.unique(diffCategory, return_counts=True)
    non_zero_values = unique_values[unique_values != 0]
    non_zero_counts = value_counts[unique_values != 0] / (
        diffCategory.shape[0] * diffCategory.shape[1]
    )
    plt.bar(non_zero_values, non_zero_counts)
    plt.title(
        "Répartition des changements de catégorie\npour: "
        + carName1
        + "\n et \n"
        + carName2
    )
    plt.savefig(
        saveDir + "/" + "decision__changes_rep" + ".png", dpi=500, bbox_inches="tight"
    )
    plt.clf()

    if interactive:
        plt.show()


def runTests():
    compareCartosGo = False
    if compareCartosGo:
        testDir = ALTI_PARENT_FOLDER + "/output/test/"

        compareCartosV2(
            testDir + "test_20_20_8.asc",
            testDir + "test_20_5_12.asc",
            5000,
            8000,
            stretch=(1, 1),
        )
        compareCartosV2(
            testDir + "test_20_10_12.asc",
            testDir + "test_20_5_12.asc",
            5000,
            8000,
            stretch=(1, 1),
        )

    generateOneCarto = False
    if generateOneCarto:
        name = "test_20_5_12"
        params = Parameters(
            cartoPrecision=5,
            innerRadius=25,
            radii=[50, 75, 100, 130, 160],
            quadrantsNb=12,
            slope=0.05,
        )
        testCartoCreator(
            params,
            currentTile=ALTI_PARENT_FOLDER
            + "/alti_data/RGEALTI_FXX_0285_6710_MNT_LAMB93_IGN69.asc",
            outputCartoPrecision=20,
            ouptutFile=ALTI_PARENT_FOLDER + "/output/test/" + name + ".asc",
            ouptutScreenShot=ALTI_PARENT_FOLDER + "/output/test/" + name + ".png",
            inputFolder=ALTI_PARENT_FOLDER + "/alti_data",
            show=True,
        )

    testBigCarto = False
    if testBigCarto:
        cqot = cartoQuerier(
            ALTI_PARENT_FOLDER + "/alti_data",
            ALTI_PARENT_FOLDER
            + "/alti_data/RGEALTI_FXX_0285_6710_MNT_LAMB93_IGN69.asc",
        )
        saveArrayToCarto(
            cqot.currentBigCarto,
            ALTI_PARENT_FOLDER + "/output/bigCarto.asc",
            {
                "ncols": 3000,
                "nrows": 3000,
                "xllcorner": 285000,
                "yllcorner": 675000,
                "cellsize": 5,
                "NODATA_value": -99999.00,
            },
        )
        plotAltiCarto(ALTI_PARENT_FOLDER + "/output/bigCarto.asc", "bigCarto")
        plt.show()

    createBulkCarto = False
    if createBulkCarto:
        bulkCartoCreation(
            ALTI_PARENT_FOLDER + "/alti_data", ALTI_PARENT_FOLDER + "/output/bulk_bv"
        )


runTests()
