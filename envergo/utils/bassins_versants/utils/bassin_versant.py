from math import pi


def calculate_bassin_versant_one_point(
    innerCircleMeanAlti, quadrants, inner_radius, radii, quadrantsNb, slope
):
    """
    Calcule le bassin versant pour un point donné.

    Args:
        innerCircleMeanAlti (float): Altitude moyenne du cercle intérieur.
        quadrants (list): Liste des quadrants contenant les altitudes.
        inner_radius (int): Rayon du cercle intérieur.
        radii (list): Liste des rayons des cercles concentriques.
        quadrantsNb (int): Nombre de quadrants.
        slope (float): Pente.

    Returns:
        float: Surface du bassin versant pour le point donné.
    """
    surfaceCount = 0

    for quadrant in quadrants:
        surfaceCount += next_quadrant_check(
            innerCircleMeanAlti, quadrant, [0, inner_radius] + radii, slope=slope
        )

    return surfaceCount / quadrantsNb


def next_quadrant_check(previousAlti, quadrant, radii, index=0, surface=0, slope=0.05):
    """
    Fonction récursive qui vérifie le prochain quadrant pour le calcul du bassin versant, et renvoie la surface de bassin versant du quadrant une fois la récursion terminée.

    Args:
        previousAlti (float): Altitude actuelle.
        quadrant (list): Liste des altitudes moyennes du quadrant.
        radii (list): Liste des rayons des cercles concentriques.
        index (int): Index actuel.
        surface (float): Surface accumulée.
        slope (float): Pente.

    Returns:
        float: Surface du bassin versant pour le quadrant donné.
    """
    if index == len(quadrant):
        return surface

    meanAlti = quadrant[index]
    if check_elevation_diff(meanAlti, previousAlti, index, radii, slope):
        surface += get_surface(index, radii)
        return next_quadrant_check(
            meanAlti, quadrant, radii, index=index + 1, surface=surface, slope=slope
        )
    return surface


def check_elevation_diff(currentAlti, previousAlti, index, radii, slope):
    """
    Vérifie la différence d'altitude pour déterminer si elle respecte le critère de pente.

    Args:
        currentAlti (float): Altitude de la partie du quadrant que l'on souhaite véirifer.
        previousAlti (float): Altitude de la partie précédente du quadrant.
        index (int): Index actuel.
        radii (list): Liste des rayons des cercles concentriques.
        slope (float): Pente.

    Returns:
        bool: True si la différence d'altitude respecte la pente, False sinon.
    """
    return 2 * (currentAlti - previousAlti) / (radii[index + 2] - radii[index]) > slope


def get_surface(index, radii):
    """
    Calcule la surface du cercle.

    Args:
        index (int): Index actuel.
        radii (list): Liste des rayons des cercles concentriques.

    Returns:
        float: Surface de la zone entre deux rayons.
    """
    return pi * radii[index + 2] ** 2 - pi * radii[index + 1] ** 2
