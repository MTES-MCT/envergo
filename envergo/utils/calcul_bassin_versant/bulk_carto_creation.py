import os
import warnings

from create_carto import createCarto
from tqdm import tqdm
from utils.carto import getCartoInfo
from utils.classes import Parameters

warnings.filterwarnings("ignore")
# ignore when numpy is trying to do the mean of an empty slice


def bulkCartoCreation(inputFolder, outputFolder, outputCartoPrecision=20):
    print("\nRunning Bulk Carto Creator in " + inputFolder + " ...\n")

    # region parameters
    params = Parameters(
        cartoPrecision=5,
        innerRadius=25,
        radii=[50, 75, 100, 130, 160],
        quadrantsNb=12,
        slope=0.05,
    )

    # endregion

    print(
        "Progression : first bar is the number of cartos, second is the current carto creation"
    )
    for file in tqdm(os.listdir(inputFolder)):
        info = getCartoInfo(inputFolder + "/" + file)
        bottomLeft = (info["xllcorner"], info["yllcorner"])
        ouptutFile = (
            outputFolder
            + "/ENVERGO_BASSSIN_VERSANT_FXX_"
            + "{:04d}".format(round(bottomLeft[0] / 1000))
            + "_"
            + "{:04d}".format(round(bottomLeft[1] / 1000))
            + "_MNT_LAMB93.asc"
        )
        createCarto(
            params,
            inputFolder + "/" + file,
            outputCartoPrecision,
            ouptutFile,
            inputFolder,
        )
