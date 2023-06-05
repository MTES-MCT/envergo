from pathlib import Path

from utils import carto
from utils.classes import Parameters
from visualization import compareCartosV2, testCartoCreator

ALTI_PARENT_FOLDER = str(Path(__file__).parent)

rayons2 = [50, 75, 100, 130, 160]
rayons1 = [50, 70, 90, 110, 130, 145, 160]
rayons0 = [59, 81, 98, 113, 126, 138, 149, 160]
rayons00 = [55, 74, 89, 102, 113, 123, 133, 142, 150, 158]

p1_12 = Parameters(
    cartoPrecision=5,
    innerRadius=25,
    radii=rayons1,
    quadrantsNb=12,
    slope=0.05,
)
p1_16 = Parameters(
    cartoPrecision=5,
    innerRadius=25,
    radii=rayons1,
    quadrantsNb=16,
    slope=0.05,
)
p0_12 = Parameters(
    cartoPrecision=5,
    innerRadius=25,
    radii=rayons0,
    quadrantsNb=12,
    slope=0.05,
)
p0_16 = Parameters(
    cartoPrecision=5,
    innerRadius=25,
    radii=rayons0,
    quadrantsNb=16,
    slope=0.05,
)
p00_12 = Parameters(
    cartoPrecision=5,
    innerRadius=25,
    radii=rayons00,
    quadrantsNb=12,
    slope=0.05,
)
p00_16 = Parameters(
    cartoPrecision=5,
    innerRadius=25,
    radii=rayons00,
    quadrantsNb=16,
    slope=0.05,
)

PARAMS = [p1_12, p0_12, p00_12, p1_16, p0_16, p00_16]

f = (p1_16, p1_12)
g = (p0_12, p1_12)
h = (p0_16, p1_16)
i = (p0_16, p0_12)
j = (p00_12, p0_12)
k = (p00_16, p0_16)


PARAMS_COMPARISON = [f, g, h, i, j, k]

PLACES = [
    [
        "44",
        ALTI_PARENT_FOLDER + "/alti_data/RGEALTI_FXX_0285_6710_MNT_LAMB93_IGN69.asc",
    ],
    [
        "39",
        ALTI_PARENT_FOLDER + "/alti_data_39/RGEALTI_FXX_0890_6625_MNT_LAMB93_IGN69.asc",
    ],
    [
        "29",
        ALTI_PARENT_FOLDER + "/alti_data_29/RGEALTI_FXX_0215_6845_MNT_LAMB93_IGN69.asc",
    ],
]


def getName(place, params: Parameters):
    bottomLeft = carto.getBottomLeftCorner(place[1])
    return (
        place[0]
        + "_"
        + str(bottomLeft[0])
        + "_"
        + str(bottomLeft[1])
        + "_test_20_"
        + str(params.cartoPrecision)
        + "_"
        + str(params.quadrantsNb)
        + "_"
        + "-".join([str(r) for r in params.radii])
    )


def getDataFolder(cartoFileName):
    return "/".join(cartoFileName.split("/")[:-1])


generate = True
if generate:
    for place in PLACES:
        for params in PARAMS:
            print("Doing : ", place, params, "\n")
            name = getName(place, params)
            testCartoCreator(
                params,
                currentTile=place[1],
                outputCartoPrecision=20,
                ouptutFile=ALTI_PARENT_FOLDER + "/output/test/" + name + ".asc",
                ouptutScreenShot=ALTI_PARENT_FOLDER + "/output/test/" + name + ".png",
                inputFolder=getDataFolder(place[1]),
                show=False,
            )

for place in PLACES:
    for params1, params2 in PARAMS_COMPARISON:
        print("Evaluating : ", place, params1, params2)
        testDir = ALTI_PARENT_FOLDER + "/output/test/"
        saveDir = (
            ALTI_PARENT_FOLDER
            + "/output/decision/"
            + place[0]
            + "_"
            + str(carto.getBottomLeftCorner(place[1])[0])
            + "_"
            + str(carto.getBottomLeftCorner(place[1])[1])
            + "/"
            + str(params1.cartoPrecision)
            + "v"
            + str(params2.cartoPrecision)
            + "_"
            + "-".join([str(p) for p in params1.radii])
            + "v"
            + "-".join([str(p) for p in params2.radii])
            + "_"
            + str(params1.quadrantsNb)
            + "v"
            + str(params2.quadrantsNb)
        )
        compareCartosV2(
            testDir + getName(place, params2) + ".asc",
            testDir + getName(place, params1) + ".asc",
            5000,
            8000,
            stretch=(1, 1),
            saveDir=saveDir,
        )
