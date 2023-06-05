from math import pi


def calculateBassinVersantOnePoint(
    innerCircleAlti, quadrants, radii, quadrantsNb, slope
):
    surfaceCount = 0

    innerCircleMeanAlti = innerCircleAlti

    for quadrant in quadrants:
        surfaceCount += nextQuadrantCheck(
            innerCircleMeanAlti, quadrant, radii, slope=slope
        )

    return surfaceCount / quadrantsNb


def nextQuadrantCheck(currentAlti, quadrant, radii, index=0, surface=0, slope=0.05):
    if index == len(quadrant):
        return surface

    meanAlti = quadrant[index]
    if checkElevationDiff(meanAlti, currentAlti, index, radii, slope):
        surface += getSurface(index, radii)
        return nextQuadrantCheck(
            meanAlti, quadrant, radii, index=index + 1, surface=surface, slope=slope
        )
    return surface


def checkElevationDiff(meanAlti, altiToCheck, index, radii, slope):
    if index == 0:
        return (meanAlti - altiToCheck) / (radii[0] / 2) > slope
    else:
        return (meanAlti - altiToCheck) / (
            (radii[index] - radii[index - 1]) / 2
        ) > slope


def getSurface(index, radii):
    if index == 0:
        return pi * radii[index] ** 2
    else:
        return pi * radii[index] ** 2 - pi * radii[index - 1] ** 2
