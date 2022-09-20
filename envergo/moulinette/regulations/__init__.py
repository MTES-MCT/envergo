import json
from functools import cached_property

from envergo.evaluations.models import RESULTS
from envergo.geodata.utils import to_geojson


class MoulinetteRegulation:
    """Run the moulinette for a single regulation (e.g Loi sur l'eau)."""

    criterion_classes = []

    def __init__(self, moulinette):
        self.moulinette = moulinette
        self.moulinette.catalog.update(self.get_catalog_data())
        self.criterions = [
            Criterion(moulinette)
            for Criterion in self.criterion_classes
            if Criterion in moulinette.criterions
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


class Map:
    """Data for a map that will be displayed with Leaflet."""

    def __init__(self, center, polygons, caption, sources, truncate=True):
        self.center = center
        self.polygons = polygons
        self.caption = caption
        self.sources = sources

        # Should we display the entire region?
        # This is used to prevent the ability to fine tune one's project and
        # get around the law by building a project at the exact limit of a
        # given zone.
        self.truncate = truncate

    def to_json(self):

        # Don't display full polygons
        EPSG_WGS84 = 4326
        buffer = self.center.buffer(850).transform(EPSG_WGS84, clone=True)

        data = json.dumps(
            {
                "center": to_geojson(self.center),
                "polygons": [
                    {
                        "polygon": to_geojson(polygon["polygon"].intersection(buffer))
                        if self.truncate
                        else to_geojson(polygon["polygon"]),
                        "color": polygon["color"],
                        "label": polygon["label"],
                    }
                    for polygon in self.polygons
                ],
                "caption": self.caption,
                "sources": [
                    {"name": map.name, "url": map.source} for map in self.sources
                ],
            }
        )
        return data


class MoulinetteCriterion:
    """Run a single moulinette check."""

    # Prevent template engine to instanciate the class since we sometimes want
    # to display the raw type for debug purpose
    do_not_call_in_templates = True

    def __init__(self, moulinette):
        self.moulinette = moulinette
        self.moulinette.catalog.update(self.get_catalog_data())

    def get_catalog_data(self):
        """Get data to inject to the global catalog."""

        return {}

    @property
    def catalog(self):
        """Is is a simple shortcut for readability purpose."""
        return self.moulinette.catalog

    @cached_property
    def result(self):
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
