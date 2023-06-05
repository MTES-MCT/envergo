import warnings

from tqdm import tqdm
from utils import carto
from utils.bassin_versant import calculateBassinVersantOnePoint
from utils.classes import Parameters

warnings.filterwarnings("ignore")
# ignore when numpy is trying to do the mean of an empty slice


def calculateBassinVersantOnPoints(
    points,
    params: Parameters,
    currentTile,
    inputFolder,
):
    results = []

    cartoMachine = carto.cartoQuerier(inputFolder, currentTile)

    OriginLessInnerCirclePoints, OriginLessQuadrantsPoints = carto.createQuadrants(
        params.cartoPrecision, params.innerRadius, params.radii, params.quadrantsNb
    )

    for point in tqdm(points, leave=False):
        if cartoMachine.queryOnePoint(point) is not None:
            innerCirclePoints = carto.updateOrigin(point, OriginLessInnerCirclePoints)

            quadrants = []
            for q in range(params.quadrantsNb):
                quadrants.append([])
                for i, _ in enumerate(params.radii):
                    quadrants[q].append([])
                    quadrants[q][i] = cartoMachine.getMeanAlti(
                        carto.updateOrigin(point, OriginLessQuadrantsPoints[q][i])
                    )

            innerCircleAlti = cartoMachine.getMeanAlti(innerCirclePoints)
            results.append(
                (
                    point,
                    calculateBassinVersantOnePoint(
                        innerCircleAlti,
                        quadrants,
                        params.radii,
                        params.quadrantsNb,
                        params.slope,
                    ),
                )
            )

        else:
            results.append((point, None))

    return results


def createCarto(
    params: Parameters,
    currentTile: str,
    outputCartoPrecision: int,
    ouptutFile: str,
    inputFolder: str,
):
    bottomLeft = carto.getBottomLeftCorner(currentTile)
    info = carto.getCartoInfo(currentTile)
    width = round(params.cartoPrecision * info["ncols"] / outputCartoPrecision)
    height = round(params.cartoPrecision * info["nrows"] / outputCartoPrecision)

    points = []
    for y in range(height):
        for x in range(width):
            points.append(
                (
                    round(bottomLeft[0] + x * outputCartoPrecision),
                    round(bottomLeft[1] + y * outputCartoPrecision),
                )
            )

    res = calculateBassinVersantOnPoints(
        points,
        params,
        currentTile,
        inputFolder,
    )

    carto.saveListToCarto(
        res,
        ouptutFile,
        {
            "ncols": width,
            "nrows": height,
            "xllcorner": bottomLeft[0],
            "yllcorner": bottomLeft[1],
            "cellsize": outputCartoPrecision,
            "NODATA_value": -99999.00,
        },
    )
