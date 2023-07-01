def get_bassin_versant_sections_one_point(
    innerCircleMeanAlti, quadrants, inner_radius, radii, slope
):
    """
    Montre les sections composant le bassin versant pour un point donné.

    Args:
        innerCircleMeanAlti (float): Altitude moyenne du cercle intérieur.
        quadrants (list): Liste des quadrants contenant les altitudes.
        inner_radius (int): Rayon du cercle intérieur.
        radii (list): Liste des rayons des cercles concentriques.
        slope (float): Pente.

    Returns:
        list(list(bool)): Sections faisant aprtie du bassin versant pour le point donné.
    """
    bassin_versant_sections = [[False] * len(q) for q in quadrants]

    for i, quadrant in enumerate(quadrants):
        bassin_versant_sections[i] = next_quadrant_check(
            innerCircleMeanAlti,
            quadrant,
            [0, inner_radius] + radii,
            bassin_versant_sections[i],
            slope=slope,
        )

    return bassin_versant_sections


def next_quadrant_check(
    previousAlti, quadrant, radii, bassin_versant_quadrant, index=0, slope=0.05
):
    """
    Fonction récursive qui vérifie le prochain quadrant pour le calcul du bassin versant, et renvoie la liste des sections composant le bassin versant du quadrant une fois la récursion terminée.

    Args:
        previousAlti (float): Altitude actuelle.
        quadrant (list): Liste des altitudes moyennes du quadrant.
        radii (list): Liste des rayons des cercles concentriques.
        index (int): Index actuel.
        bassin_versant_quadrant (list(bool)): Sections accumulées.
        slope (float): Pente.

    Returns:
        list(bool): Sections composant le bassin versant pour le quadrant donné.
    """
    if index == len(quadrant):
        return bassin_versant_quadrant

    meanAlti = quadrant[index]
    if check_elevation_diff(meanAlti, previousAlti, index, radii, slope):
        bassin_versant_quadrant[index] = True
        return next_quadrant_check(
            meanAlti,
            quadrant,
            radii,
            index=index + 1,
            bassin_versant_quadrant=bassin_versant_quadrant,
            slope=slope,
        )
    return bassin_versant_quadrant


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