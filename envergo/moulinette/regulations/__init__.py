import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace

from django.contrib.gis.geos import GEOSGeometry

from envergo.evaluations.models import RESULT_CASCADE, RESULTS, TAG_STYLES_BY_RESULT
from envergo.geodata.utils import EPSG_WGS84, merge_geometries, to_geojson


class Stake(Enum):
    SOUMIS = "Soumis"
    INTERDIT = "Interdit"


@dataclass
class RequiredAction:
    stake: Stake
    text: str

    def __str__(self):
        return self.text


@dataclass
class MapPolygon:
    """Data that can be displayed and labeled on a leaflet map as a polygon.

    A `MapPolygon is meant to represent a single entry on a map:
    a polygon with a given color and label.
    """

    perimeters: list  # List of objects with a `geometry` property
    color: str
    label: str
    class_name: str = ""  # CSS class name to apply to the polygon

    @property
    def geometry(self):
        geometries = [p.geometry for p in self.perimeters]
        merged_geometry = merge_geometries(geometries)
        return merged_geometry

    @property
    def maps(self):
        from envergo.geodata.models import Map as geodata_Map

        perimeter_maps = []
        for p in self.perimeters:
            if hasattr(p, "map"):
                perimeter_maps.append(p.map)
            elif isinstance(p, geodata_Map):
                perimeter_maps.append(p)
        return perimeter_maps


@dataclass
class Map:
    """Data for a map that will be displayed with Leaflet."""

    center: tuple  # Coordinates to center the map
    entries: list  # List of `MapPolygon` objects
    caption: str = None  # Legend displayed below the map
    truncate: bool = True  # Should the displayed polygons be truncated?
    zoom: int = 17  # the map zoom to pass to leaflet
    zoom_on_geometry: MapPolygon = (
        None  # Polygon to zoom on when the map is loaded. If set, center and zoom level are ignored
    )
    display_marker_at_center: bool = True  # Add a Map Marker at the center of the map
    ratio_classes: str = (
        "ratio-4x3 ratio-sm-4x5"  # Check for "project.scss" for available ratios
    )
    fixed: bool = True  # Is the map fixed or can it be zoomed and dragged?
    type: str = "criterion"  # Can be "criterion" or "regulation"

    def to_json(self):
        # Don't display full polygons
        EPSG_WGS84 = 4326
        buffer = self.center.buffer(1000).transform(EPSG_WGS84, clone=True)

        data = json.dumps(
            {
                "type": self.type,
                "center": to_geojson(self.center),
                "zoom": self.zoom,
                "polygons": [
                    {
                        "polygon": (
                            to_geojson(entry.geometry.intersection(buffer))
                            if self.truncate
                            else to_geojson(entry.geometry)
                        ),
                        "color": entry.color,
                        "label": entry.label,
                        "className": entry.class_name,
                    }
                    for entry in self.entries
                ],
                "caption": self.caption,
                "sources": [
                    {"name": map.name, "url": map.source} for map in self.sources
                ],
                "fixed": self.fixed,
                "zoomOnGeometry": (
                    to_geojson(self.zoom_on_geometry.geometry)
                    if self.zoom_on_geometry
                    else None
                ),
                "displayMarkerAtCenter": self.display_marker_at_center,
            }
        )
        return data

    @property
    def sources(self):
        maps = set()
        for entry in self.entries:
            for map in entry.maps:
                maps.add(map)
        return maps


class MapFactory(ABC):
    """A factory that creates a map."""

    def __init__(self, regulation):
        self.regulation = regulation

        # We use visually distinctive color palette to display perimeters.
        # https://d3js.org/d3-scale-chromatic/categorical#schemeTableau10
        self.palette = [
            self.regulation.polygon_color,
            "#4e79a7",
            "#e15759",
            "#76b7b2",
            "#59a14f",
            "#edc949",
            "#af7aa1",
            "#ff9da7",
            "#9c755f",
            "#bab0ab",
        ]

    def create_perimeter_polygons(self):
        """Create MapPolygon objects from perimeters."""

        perimeters = self.regulation.perimeters.all()
        polygons = None
        if perimeters:
            polygons = [
                MapPolygon(
                    [perimeter],
                    self.palette[counter % len(self.palette)],
                    perimeter.map_legend,
                )
                for counter, perimeter in enumerate(perimeters)
            ]

        return polygons

    @abstractmethod
    def create_map(self) -> Map | None:
        """Create a map."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def human_readable_name(cls):
        raise NotImplementedError


class PerimetersBoundedWithCenterMapMarkerMapFactory(MapFactory):
    """A factory that creates a map with a marker on project center and bounded by perimeters."""

    @classmethod
    def human_readable_name(cls):
        return "Une carte montrant l’ensemble des périmètres, avec un marqueur sur le centre du projet"

    def create_map(self) -> Map | None:
        """Create a map centered on moulinette location."""
        polygons = self.create_perimeter_polygons()

        if polygons:
            map = Map(
                type="regulation",
                center=self.regulation.moulinette.get_map_center(),
                entries=polygons,
                truncate=False,
                display_marker_at_center=True,
                zoom=None,
                ratio_classes="ratio-2x1 ratio-sm-4x5",
                fixed=False,
            )
            return map

        return None


class HedgesToRemoveCentricMapFactory(MapFactory):
    """A factory that creates a map centered on the hedges to remove."""

    @classmethod
    def human_readable_name(cls):
        return "Une carte centrée sur les haies à détruire (GUH uniquement)"

    def create_map(self) -> Map | None:
        """Create a map centered on the hedges to remove."""
        polygons = self.create_perimeter_polygons()
        if polygons:
            haies = self.regulation.moulinette.catalog.get("haies")
            if haies:
                hedges_to_remove = MapPolygon(
                    [
                        SimpleNamespace(
                            geometry=GEOSGeometry(hedge.geometry.wkt, srid=EPSG_WGS84)
                        )
                        for hedge in haies.hedges_to_remove()
                    ],
                    "red",
                    "Haies à détruire",
                    class_name="hedge to-remove",
                )

                polygons.append(hedges_to_remove)

                map = Map(
                    type="regulation",
                    center=self.regulation.moulinette.get_map_center(),
                    entries=polygons,
                    truncate=False,
                    zoom_on_geometry=hedges_to_remove,
                    display_marker_at_center=False,
                    zoom=None,
                    ratio_classes="ratio-2x1 ratio-sm-4x5",
                    fixed=False,
                )
                return map

        return None


class HedgesCentricMapFactory(MapFactory):
    """A factory that creates a map centered on the hedges (both to remove, and to plant)."""

    @classmethod
    def human_readable_name(cls):
        return "Une carte centrée sur les haies, à la fois à détruire et à planter (GUH uniquement)"

    def create_map(self) -> Map | None:
        """Create a map centered on the hedges."""
        polygons = self.create_perimeter_polygons()
        if polygons:
            haies = self.regulation.moulinette.catalog.get("haies")
            if haies:
                hedges_to_remove_geometries = [
                    SimpleNamespace(
                        geometry=GEOSGeometry(hedge.geometry.wkt, srid=EPSG_WGS84)
                    )
                    for hedge in haies.hedges_to_remove()
                ]
                hedges_to_plant_geometries = [
                    SimpleNamespace(
                        geometry=GEOSGeometry(hedge.geometry.wkt, srid=EPSG_WGS84)
                    )
                    for hedge in haies.hedges_to_plant()
                ]

                if hedges_to_plant_geometries:
                    hedges_to_plant = MapPolygon(
                        hedges_to_plant_geometries,
                        "#0f0",
                        "Haies à planter",
                        class_name="hedge to-plant",
                    )
                    polygons.append(hedges_to_plant)

                if hedges_to_remove_geometries:
                    hedges_to_remove = MapPolygon(
                        hedges_to_remove_geometries,
                        "#f00",
                        "Haies à détruire",
                        class_name="hedge to-remove",
                    )
                    polygons.append(hedges_to_remove)

                hedges = MapPolygon(
                    hedges_to_remove_geometries + hedges_to_plant_geometries,
                    "",
                    "",
                    class_name="",
                )

                return Map(
                    type="regulation",
                    center=self.regulation.moulinette.get_map_center(),
                    entries=polygons,
                    truncate=False,
                    zoom_on_geometry=hedges,
                    display_marker_at_center=False,
                    zoom=None,
                    ratio_classes="ratio-2x1 ratio-sm-4x5",
                    fixed=False,
                )

        return None


class RegulationEvaluator(ABC):
    """Evaluate a single regulation."""

    do_not_call_in_templates = True
    choice_label = "Défaut"

    def __init__(self, moulinette):
        self.moulinette = moulinette

    def evaluate(self, regulation):
        self._result = self.get_result(regulation)

    def get_result(self, regulation):
        """Compute global result from individual criteria.

        When we perform an evaluation, a single regulation has many criteria.
        Criteria can have different results, but we display a single value for
        the regulation result.

        We can reduce different criteria results into a single regulation
        result because results have different priorities.

        For example, if a single criterion has the "interdit" result, the
        regulation result will be "interdit" too, no matter what the other
        criteria results are. Then it will be "soumis", etc.

        Different regulations have different set of possible result values, e.g
        only the Évaluation environnementale regulation has the "cas par cas" or
        "systematique" results, but the cascade still works.
        """

        # We start by handling edge cases:
        # - when the regulation is not activated for the department
        # - when the perimeter is not activated
        # - when no perimeter is found
        if not regulation.is_activated():
            return RESULTS.non_active

        if regulation.has_perimeters:
            all_perimeters = regulation.perimeters.all()
            activated_perimeters = [p for p in all_perimeters if p.is_activated]
            if all_perimeters and not any(activated_perimeters):
                return RESULTS.non_disponible
            if not all_perimeters:
                return RESULTS.non_concerne

        # From this point, we made sure every data (regulation, perimeter) is existing
        # and activated

        results = [criterion.result for criterion in regulation.criteria.all()]
        result = None
        for status in RESULT_CASCADE:
            if status in results:
                result = status
                break

        # If there is no criterion at all, we have to set a default value
        if result is None:
            if regulation.has_perimeters:
                result = RESULTS.non_soumis
            else:
                result = RESULTS.non_disponible
        return result

    @property
    def result(self):
        """Return the regulation macro result."""

        if not hasattr(self, "_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._result


class AmenagementRegulationEvaluator(RegulationEvaluator):
    """Specific evaluator for the amenagement site."""

    choice_label = "Aménagement > Défaut"


class HaieRegulationEvaluator(RegulationEvaluator):
    """Specific evaluator for the haies site."""

    choice_label = "Haie > Défaut"

    # result -> autorisation / déclaration
    PROCEDURE_TYPE_MATRIX = {}

    def evaluate(self, regulation):
        super().evaluate(regulation)
        self._procedure_type = self.get_procedure_type(regulation)

    def get_procedure_type(self, regulation):
        procedure_type = self.PROCEDURE_TYPE_MATRIX.get(self.result)
        return procedure_type

    @property
    def procedure_type(self):
        """Return the regulation procedure_type (autorisation / déclaration)."""
        if not hasattr(self, "_procedure_type"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._procedure_type


class CriterionEvaluator(ABC):
    """Evaluate a single criterion.

    The basic workflow is has follow:

     - make sure the data we need is available (`get_catalog_data`) and inject
       it to the global catalog, to avoid duplicate queries from other criteria
     - get the data we need to perform the check (`get_result_data`)
     - convert the data to a single result code using the `CODE_MATRIX` dict
     - convert the result code to a single result using the `RESULT_MATRIX` dict

    Those operations are performed in the `evaluate` method, which should only
    be called once, and that populates the `result_code` and `result` properties.
    """

    # Prevent template engine to instanciate the class since we sometimes want
    # to display the raw type for debug purpose
    do_not_call_in_templates = True

    # Associate evaluation data with a single result code
    CODE_MATRIX = {}

    # Associate a result code with a single result
    RESULT_MATRIX = {}

    # The form class to use to ask the end user for additional data
    form_class = None

    # The form class to use to ask the admin for necessary settings
    settings_form_class = None

    def __init__(self, moulinette, distance, settings):
        """Initialize the evaluator.

        Args:
            moulinette (Moulinette): The moulinette instance.
            distance (int): The distance to the queried coordinates.
            settings (dict): Custom settings required for computing the result, set in the admin.
        """
        if not hasattr(self, "slug"):
            raise RuntimeError(
                f"CriterionEvaluator {type(self).__name__} must have a `slug` attribute."
            )
        self.moulinette = moulinette
        self.distance = distance
        self.moulinette.catalog.update(self.get_catalog_data())
        self.settings = settings

    @property
    def catalog(self):
        """Is is a simple shortcut for readability purpose."""
        return self.moulinette.catalog

    def get_catalog_data(self):
        """Get data to inject to the global catalog."""

        form = self.get_form()
        if form and form.is_valid():
            if hasattr(form, "prefixed_cleaned_data"):
                data = form.prefixed_cleaned_data
            else:
                data = form.cleaned_data
        else:
            data = {}

        return data

    def get_result_data(self):
        """Return the data used to perform the criterion check."""

        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_result_data` method."
        )

    def get_result_code(self, result_data):
        """Compute a unique result code from criterion data."""

        result_code = self.CODE_MATRIX.get(result_data)
        return result_code

    def get_result(self, result_code):
        """Converts a unique result code to a single result label."""

        result = self.RESULT_MATRIX.get(result_code, result_code)
        return result

    def evaluate(self):
        """Perform the criterion check.

        This method is called once and saves the result codes.

        The result code is a unique code used to select the template to render.
        The result is a somewhat standard value like "non_soumis", "action_requise", etc.
        """

        # Before performing the check, we need to make sure we have all the data
        # we need.
        # We might require additional data:
        # - from the user, using an "additional data" form
        # - from the admin, using a "settings" form
        form = self.get_form()
        settings_form = self.get_settings_form()
        if not all(
            (
                form is None or form.is_valid(),
                settings_form is None or settings_form.is_valid(),
            )
        ):
            self._result_code, self._result = (
                RESULTS.non_disponible,
                RESULTS.non_disponible,
            )
            return

        result_data = self.get_result_data()
        result_code = self.get_result_code(result_data)
        result = self.get_result(result_code)
        self._result_code, self._result = result_code, result

    @property
    def result_code(self):
        """Return the criterion result code.

        The result code is a unique code used to render the criterion template.

        This is useful because for a given result, a single criterion could be
        rendered in different ways. E.g a criterion could have a "action requise"
        result, but the action is different depending on the criterion parameters.

        """
        if not hasattr(self, "_result_code"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._result_code

    @property
    def result(self):
        """Return the criterion result.

        This value is used to render the criterion result label (e.g "action requise")
        and to compute the whole regulation result.
        """
        if not hasattr(self, "_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._result

    @property
    def result_tag_style(self):
        """Define the style (mainly the color) of the result tag."""

        return TAG_STYLES_BY_RESULT[self.result]

    def get_map(self):
        """Returns a `Map` object."""
        return None

    def get_form(self):
        """Get the form to ask the user for additional data."""

        form_class = getattr(self, "form_class", None)
        if form_class:
            form = self.form_class(**self.moulinette.form_kwargs)
        else:
            form = None
        return form

    def get_settings_form(self):
        """Get the form to ask the admin for necessary settings."""

        settings_form_class = getattr(self, "settings_form_class", None)
        if settings_form_class:
            if self.settings:
                form = self.settings_form_class(self.settings)
            else:
                form = self.settings_form_class()
        else:
            form = None
        return form


SELF_DECLARATION_ELIGIBILITY_MATRIX = {
    RESULTS.soumis: True,
    RESULTS.soumis_ou_pac: True,
    RESULTS.non_soumis: False,
    RESULTS.action_requise: True,
    RESULTS.non_disponible: False,
    RESULTS.cas_par_cas: True,
    RESULTS.systematique: True,
    RESULTS.non_applicable: False,
    RESULTS.non_concerne: False,
    RESULTS.a_verifier: True,
    RESULTS.iota_a_verifier: True,
    RESULTS.interdit: True,
    RESULTS.non_active: False,
    RESULTS.derogation_inventaire: False,
    RESULTS.derogation_simplifiee: False,
    RESULTS.dispense: False,
    RESULTS.dispense_sous_condition: False,
    RESULTS.soumis_declaration: False,
    RESULTS.soumis_autorisation: False,
}


_missing_results = [
    key for (key, label) in RESULTS if key not in SELF_DECLARATION_ELIGIBILITY_MATRIX
]
if _missing_results:
    raise ValueError(
        f"The following RESULTS are missing in SELF_DECLARATION_ELIGIBILITY_MATRIX: {_missing_results}"
    )


class SelfDeclarationMixin:
    """Mixin for criterion evaluators that need to display the "self declare" call to action."""

    @property
    def eligible_to_self_declaration(self):
        """Should we display the "self declare" call to action?"""
        if not hasattr(self, "_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")
        return SELF_DECLARATION_ELIGIBILITY_MATRIX[self._result]


class HedgeDensityMixin:
    """Mixin for criterion evaluators that need "hedge density" to be evaluated."""

    pass


class ActionsToTakeMixin:
    """Mixin for evaluators (for both criterion and regulation) that project result into actions to take."""

    ACTIONS_TO_TAKE_MATRIX = {}

    def get_actions_to_take(self):
        actions_to_take = self.ACTIONS_TO_TAKE_MATRIX.get(self.result, [])
        return actions_to_take

    @property
    def actions_to_take(self):
        """Return the actions to take depending on regulation result."""
        if not hasattr(self, "_actions_to_take"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._actions_to_take

    def evaluate(self, *args):
        super().evaluate(*args)
        self._actions_to_take = self.get_actions_to_take()
