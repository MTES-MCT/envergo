"""Shared test utilities for moulinette tests.

Provides helpers to reduce boilerplate when constructing moulinette test data,
creating regulation/criterion combos, and building hedge scenarios.
"""

from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.tests.factories import CriterionFactory, RegulationFactory

# ---------------------------------------------------------------------------
# Coordinate presets
# ---------------------------------------------------------------------------
# Named presets give semantic meaning to hard-coded coordinates.
# Each is a (lat, lng) tuple inside a known geographic area.

# Mouais, Loire-Atlantique (department 44)
COORDS_MOUAIS = (47.696706, -1.646947)

# Nantes area, Loire-Atlantique (department 44) — used in view tests
COORDS_NANTES = (47.21381, -1.54394)

# Hérault (department 34)
COORDS_HERAULT = (43.58, 3.26)

# Calvados / Normandie (department 14)
COORDS_NORMANDIE = (49.13989, -0.17184)

# Bizous town center (department 65) — pairs of (lat, lng) representing hedge
# start/end points, used in perimeter-based haie tests.
COORDS_BIZOUS_INSIDE = [
    (43.06930871579473, 0.4421436860179369),
    (43.069162248282396, 0.44236765047068033),
]
COORDS_BIZOUS_EDGE = [
    (43.069807900393826, 0.4426179348420038),
    (43.068048918563875, 0.4415625648710002639653),
]
COORDS_BIZOUS_OUTSIDE = [
    (43.09248072614743, 0.48007431760217484),
    (43.09280782621999, 0.48095944654749073),
]

# Bizou, Orne (department 61) — used in amenagement tests (evalenv, natura2000)
COORDS_BIZOU = (48.496195, 0.750409)


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------


def make_amenagement_data(
    lat=COORDS_MOUAIS[0],
    lng=COORDS_MOUAIS[1],
    created_surface=200,
    final_surface=200,
    existing_surface=0,
    **extra,
):
    """Build a MoulinetteAmenagement-compatible data dict.

    Returns the {"initial": data, "data": data} wrapper expected by
    MoulinetteAmenagement.__init__.
    """
    data = {
        "lat": lat,
        "lng": lng,
        "existing_surface": existing_surface,
        "created_surface": created_surface,
        "final_surface": final_surface,
        **extra,
    }
    return {"initial": data, "data": data}


def make_hedge(
    coords=None,
    hedge_id="D1",
    hedge_type="TO_REMOVE",
    type_haie="degradee",
    sur_parcelle_pac=False,
    **additional_data_overrides,
):
    """Build a single hedge dict suitable for HedgeDataFactory(data=[...]).

    `coords` is a list of (lat, lng) tuples representing the hedge polyline.
    Defaults to COORDS_BIZOUS_INSIDE when omitted.
    """
    if coords is None:
        coords = COORDS_BIZOUS_INSIDE
    return {
        "id": hedge_id,
        "type": hedge_type,
        "latLngs": [{"lat": lat, "lng": lng} for lat, lng in coords],
        "additionalData": {
            "type_haie": type_haie,
            "vieil_arbre": False,
            "proximite_mare": False,
            "sur_parcelle_pac": sur_parcelle_pac,
            "proximite_point_eau": False,
            "connexion_boisement": False,
            **additional_data_overrides,
        },
    }


def make_haie_data(
    hedges=None,
    hedge_data=None,
    motif="chemin_acces",
    reimplantation="remplacement",
    localisation_pac="non",
    travaux="destruction",
    element="haie",
    department="44",
    **extra,
):
    """Build a MoulinetteHaie-compatible data dict.

    If `hedge_data` is provided, it is passed directly to
    HedgeDataFactory(data=...) — use this with dicts from make_hedge().

    Otherwise, if `hedges` is not provided, creates a default HedgeData with
    a single short hedge (sur_parcelle_pac=False). Pass a HedgeData instance
    or a list of Hedge objects (which will be wrapped in a HedgeDataFactory).

    Returns the {"initial": data, "data": data} wrapper expected by
    MoulinetteHaie.__init__.
    """
    if hedge_data is not None:
        hedges = HedgeDataFactory(data=hedge_data)
    elif hedges is None:
        hedges = HedgeDataFactory(
            hedges=[HedgeFactory(length=4, additionalData={"sur_parcelle_pac": False})]
        )
    elif isinstance(hedges, list):
        hedges = HedgeDataFactory(hedges=hedges)

    data = {
        "element": element,
        "travaux": travaux,
        "motif": motif,
        "reimplantation": reimplantation,
        "localisation_pac": localisation_pac,
        "haies": hedges,
        "department": department,
        **extra,
    }
    return {"initial": data, "data": data}


# ---------------------------------------------------------------------------
# Criterion setup helpers
# ---------------------------------------------------------------------------
# Each function creates a Regulation + its associated Criteria and returns
# them as a tuple (regulation, [criteria]). These replace the repetitive
# autouse fixtures duplicated across test files.


def setup_loi_sur_leau(activation_map, include_optional=True):
    """Create Loi sur l'eau regulation with standard criteria."""
    regulation = RegulationFactory(
        regulation="loi_sur_leau",
        evaluator="envergo.moulinette.regulations.loisurleau.LoiSurLEauRegulation",
    )
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.ZoneHumide",
            activation_map=activation_map,
        ),
        CriterionFactory(
            title="Zone inondable",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.ZoneInondable",
            activation_map=activation_map,
        ),
        CriterionFactory(
            title="Ruissellement",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.loisurleau.Ruissellement",
            activation_map=activation_map,
        ),
    ]
    if include_optional:
        criteria.extend(
            [
                CriterionFactory(
                    title="Écoulement EP sans BV",
                    regulation=regulation,
                    evaluator="envergo.moulinette.regulations.loisurleau.EcoulementSansBV",
                    activation_map=activation_map,
                    is_optional=True,
                ),
                CriterionFactory(
                    title="Écoulement EP avec BV",
                    regulation=regulation,
                    evaluator="envergo.moulinette.regulations.loisurleau.EcoulementAvecBV",
                    activation_map=activation_map,
                    is_optional=True,
                ),
            ]
        )
    return regulation, criteria


def setup_conditionnalite_pac(activation_map):
    """Create Conditionnalité PAC regulation with BCAE8 criterion."""
    regulation = RegulationFactory(regulation="conditionnalite_pac")
    criteria = [
        CriterionFactory(
            title="BCAE 8",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
            activation_map=activation_map,
            activation_mode="department_centroid",
        ),
    ]
    return regulation, criteria


def setup_ep(activation_map, activation_mode="department_centroid"):
    """Create Espèces protégées regulation with simple criterion."""
    regulation = RegulationFactory(regulation="ep")
    criteria = [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesSimple",
            activation_map=activation_map,
            activation_mode=activation_mode,
        ),
    ]
    return regulation, criteria


def setup_eval_env(activation_map):
    """Create Évaluation environnementale regulation with standard criteria."""
    regulation = RegulationFactory(
        regulation="eval_env",
        evaluator="envergo.moulinette.regulations.evalenv.EvalEnvRegulation",
    )
    criteria = [
        CriterionFactory(
            title="Terrain d'assiette",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.TerrainAssiette",
            activation_map=activation_map,
        ),
        CriterionFactory(
            title="Emprise",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.Emprise",
            activation_map=activation_map,
        ),
        CriterionFactory(
            title="Surface plancher",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.evalenv.SurfacePlancher",
            activation_map=activation_map,
        ),
    ]
    return regulation, criteria


def setup_natura2000(activation_map):
    """Create Natura 2000 regulation with standard criteria."""
    regulation = RegulationFactory(
        regulation="natura2000",
        evaluator="envergo.moulinette.regulations.natura2000.Natura2000Regulation",
    )
    criteria = [
        CriterionFactory(
            title="Zone humide",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.ZoneHumide",
            activation_map=activation_map,
        ),
        CriterionFactory(
            title="Zone inondable",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.ZoneInondable",
            activation_map=activation_map,
        ),
        CriterionFactory(
            title="IOTA",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.natura2000.IOTA",
            activation_map=activation_map,
        ),
    ]
    return regulation, criteria
