from math import pi


def calculate_bassin_versant_one_point(
    innerCircleAlti, quadrants, radii, quadrantsNb, slope
):
    surfaceCount = 0

    innerCircleMeanAlti = innerCircleAlti

    for quadrant in quadrants:
        surfaceCount += next_quadrant_check(
            innerCircleMeanAlti, quadrant, radii, slope=slope
        )

    return surfaceCount / quadrantsNb


def next_quadrant_check(currentAlti, quadrant, radii, index=0, surface=0, slope=0.05):
    if index == len(quadrant):
        return surface

    meanAlti = quadrant[index]
    if check_elevation_diff(meanAlti, currentAlti, index, radii, slope):
        surface += get_surface(index, radii)
        return next_quadrant_check(
            meanAlti, quadrant, radii, index=index + 1, surface=surface, slope=slope
        )
    return surface


def check_elevation_diff(meanAlti, altiToCheck, index, radii, slope):
    if index == 0:
        return (meanAlti - altiToCheck) / (radii[0] / 2) > slope
    else:
        return (meanAlti - altiToCheck) / (
            (radii[index] - radii[index - 1]) / 2
        ) > slope


def get_surface(index, radii):
    if index == 0:
        return pi * radii[index] ** 2
    else:
        return pi * radii[index] ** 2 - pi * radii[index - 1] ** 2
