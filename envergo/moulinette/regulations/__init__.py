import json
from abc import ABC
from dataclasses import dataclass
from enum import Enum

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


@dataclass
class MapPolygon:
    """Data that can be displayed and labeled on a leaflet map as a polygon.

    A `MapPolygon is meant to represent a single entry on a map:
    a polygon with a given color and label.
    """

    perimeters: list  # List of objects with a `geometry` property
    color: str
    label: str

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

    def __init__(self, moulinette, distance):
        """Initialize the evaluator.

        Args:
            moulinette (Moulinette): The moulinette instance.
            distance (int): The distance to the queried coordinates.
        """
        self.moulinette = moulinette
        self.distance = distance
        self.moulinette.catalog.update(self.get_catalog_data())

    @property
    def catalog(self):
        """Is is a simple shortcut for readability purpose."""
        return self.moulinette.catalog

    def get_catalog_data(self):
        """Get data to inject to the global catalog."""

        form = self.get_form()
        if form and form.is_valid():
            data = form.cleaned_data
        else:
            data = {}

        return data

    def get_result_data(self):
        """Return the data used to perform the criterion check."""

        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_result_data` method."
        )

    def evaluate(self):
        form = self.get_form()
        if (form and form.is_valid()) or form is None:
            result_data = self.get_result_data()
            result_code = self.CODE_MATRIX.get(result_data)
            result = self.RESULT_MATRIX.get(result_code, result_code)
            self._result_code, self._result = result_code, result
        else:
            self._result_code, self._result = (
                RESULTS.non_disponible,
                RESULTS.non_disponible,
            )

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

    def get_map(self):
        """Returns a `Map` object."""
        return None

    def get_form_class(self):
        form_class = getattr(self, "form_class", None)
        return form_class

    def get_form(self):
        if hasattr(self, "form_class"):
            form = self.form_class(self.moulinette.raw_data)
        else:
            form = None
        return form
