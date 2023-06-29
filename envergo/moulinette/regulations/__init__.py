import json
from abc import ABC
from dataclasses import dataclass
from enum import Enum
from functools import cached_property

from envergo.evaluations.models import RESULTS
from envergo.geodata.utils import merge_geometries, to_geojson


class Stake(Enum):
    SOUMIS = "Soumis"
    INTERDIT = "Interdit"


@dataclass
class RequiredAction:
    stake: Stake
    text: str

    def __str__(self):
        return self.text


class MoulinetteRegulation(ABC):
    """Run the moulinette for a single regulation (e.g Loi sur l'eau).

    This class is meant to be inherited to implement actual regulations.
    """

    # Implement this in subclasses
    criterion_classes = []

    def __init__(self, moulinette):
        self.moulinette = moulinette
        self.moulinette.catalog.update(self.get_catalog_data())

        # Instanciate the criterions
        self.criterions = [
            perimeter.criterion(moulinette, perimeter)
            for perimeter in moulinette.perimeters
            if perimeter.criterion in self.criterion_classes
        ]

    def get_catalog_data(self):
        """Get data to inject to the global catalog."""

        return {}

    @property
    def catalog(self):
        """Is is a simple shortcut for readability purpose."""
        return self.moulinette.catalog

    @cached_property
    def result(self):
        """Compute global result from individual criterions."""

        results = [criterion.result for criterion in self.criterions]

        if RESULTS.soumis in results:
            result = RESULTS.soumis
        elif RESULTS.action_requise in results:
            result = RESULTS.action_requise
        else:
            result = RESULTS.non_soumis

        return result

    def required_actions(self):
        actions = [c.required_action() for c in self.criterions if c.required_action()]
        return actions

    def required_actions_soumis(self):
        actions = [
            action for action in self.required_actions() if action.stake == Stake.SOUMIS
        ]
        return actions

    def required_actions_interdit(self):
        actions = [
            action
            for action in self.required_actions()
            if action.stake == Stake.INTERDIT
        ]
        return actions

    def project_impacts(self):
        impacts = [c.project_impact() for c in self.criterions if c.project_impact()]
        return impacts

    def discussion_contacts(self):
        contacts = [
            c.discussion_contact() for c in self.criterions if c.discussion_contact()
        ]
        return contacts

    def __getattr__(self, attr):
        """Returs the corresponding criterion.

        Allows to do something like this:
        moulinette.loi_sur_leau.zones_inondables to fetch the correct criterion.
        """
        return self.get_criterion(attr)

    def get_criterion(self, criterion_slug):
        """Return the regulation with the given slug."""

        def select_criterion(criterion):
            return criterion.slug == criterion_slug

        criterion = next(filter(select_criterion, self.criterions), None)
        return criterion

    @cached_property
    def map(self):
        try:
            map = self._get_map()
        except:  # noqa
            map = None
        return map

    def _get_map(self):
        return None


@dataclass
class MapPolygon:
    """Data that can be displayed and labeled on a leaflet map as a polygon.

    A `MapPolygon is meant to represent a single entry on a map:
    a polygon with a given color and label.
    """

    perimeters: list  # List of `envergo.geofr.Perimeter` objects
    color: str
    label: str

    @property
    def geometry(self):
        geometries = [p.geometry for p in self.perimeters]
        merged_geometry = merge_geometries(geometries)
        return merged_geometry

    @property
    def maps(self):
        perimeter_maps = [p.map for p in self.perimeters]
        return perimeter_maps


@dataclass
class Map:
    """Data for a map that will be displayed with Leaflet."""

    center: tuple  # Coordinates to center the map
    entries: list  # List of `MapPolygon` objects
    caption: str  # Legend displayed below the map
    truncate: bool = True  # Should the displayed polygons be truncated?
    zoom: int = 16  # the map zoom to pass to leaflet

    def to_json(self):
        # Don't display full polygons
        EPSG_WGS84 = 4326
        buffer = self.center.buffer(1000).transform(EPSG_WGS84, clone=True)

        data = json.dumps(
            {
                "center": to_geojson(self.center),
                "zoom": self.zoom,
                "polygons": [
                    {
                        "polygon": to_geojson(
                            entry.geometry.buffer(0).intersection(buffer)
                        )
                        if self.truncate
                        else to_geojson(entry.geometry.buffer(0)),
                        "color": entry.color,
                        "label": entry.label,
                    }
                    for entry in self.entries
                ],
                "caption": self.caption,
                "sources": [
                    {"name": map.name, "url": map.source} for map in self.sources
                ],
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


class MoulinetteCriterion(ABC):
    """Run a single moulinette check."""

    # Prevent template engine to instanciate the class since we sometimes want
    # to display the raw type for debug purpose
    do_not_call_in_templates = True

    # This is the list of all unique result codes the criterion can return.
    # This is onlyy used for debugging purpose in the `envergo.moulinette.forms.MoulinetteDebug` form.
    # Every subclass should override this property to match the
    # "Nomenclature réglementations & critères" document.
    CODES = ["soumis", "non_soumis", "action_requise", "non_concerne"]

    def __init__(self, moulinette, perimeter):
        self.moulinette = moulinette
        self.moulinette.catalog.update(self.get_catalog_data())
        self.perimeter = perimeter

    def get_catalog_data(self):
        """Get data to inject to the global catalog."""

        return {}

    @property
    def catalog(self):
        """Is is a simple shortcut for readability purpose."""
        return self.moulinette.catalog

    @cached_property
    def result(self):
        """The result will be displayed to the user with a fancy label."""
        return self.result_code

    @property
    def result_code(self):
        """Return a unique code for the criterion result.

        Sometimes, a same criterion can have the same result for different reasons.
        Because of this, we want unique codes to display custom messages to
        the user.
        """
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.result_code` method."
        )

    @cached_property
    def map(self):
        try:
            map = self._get_map()
        except:  # noqa
            map = None
        return map

    def _get_map(self):
        return None

    def get_form(self):
        if hasattr(self, "form_class"):
            form = self.form_class(self.moulinette.raw_data)
        else:
            form = None
        return form

    def required_action(self):
        return None

    def project_impact(self):
        return None

    def discussion_contact(self):
        return None


class CriterionEvaluator(ABC):
    """Evaluate a single criterion."""

    # Associate evaluation data with a single result code
    CODE_MATRIX = {}

    # Associate a result code with a single result
    RESULT_MATRIX = {}

    def __init__(self, moulinette):
        self.moulinette = moulinette
        self.moulinette.catalog.update(self.get_catalog_data())

    @property
    def catalog(self):
        """Is is a simple shortcut for readability purpose."""
        return self.moulinette.catalog

    def get_catalog_data(self):
        """Get data to inject to the global catalog."""

        return {}

    def get_result_data(self):
        """Return the data used to perform the criterion check."""

        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_result_data` method."
        )

    def evaluate(self):
        result_data = self.get_result_data()
        result_code = self.CODE_MATRIX.get(result_data)
        result = self.RESULT_MATRIX.get(result_code, result_code)
        self._result_code, self._result = result_code, result

    @property
    def result_code(self):
        """Return the criterion result code."""
        if not hasattr(self, "_result_code"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._result_code

    @property
    def result(self):
        """Return the criterion result."""
        if not hasattr(self, "_result"):
            raise RuntimeError("Call the evaluator `evaluate` method first")

        return self._result
