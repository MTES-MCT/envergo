from math import ceil

import shapely
from django import forms
from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.aggregates import Union
from django.contrib.gis.geos import MultiLineString
from django.db.models.functions import Cast
from pyproj import Geod

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class Natura2000HaieRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Natura 2000"

    PROCEDURE_TYPE_MATRIX = {
        "soumis": "declaration",
        "non_concerne": "declaration",
        "non_soumis": "declaration",
    }


class Natura2000HaieSettings(forms.Form):
    result = forms.ChoiceField(
        label="Resultat attendu de l'évaluateur",
        help_text="Indique si l’arrachage de haies est soumis à évaluation des incidences Natura 2000 pour ce critère.",
        required=True,
        choices=RESULTS,
    )


EPSG_WGS84 = 4326
EPSG_LAMB93 = 2154


class Natura2000Haie(CriterionEvaluator):
    choice_label = "Natura 2000 > Haie"
    slug = "natura2000_haie"
    settings_form_class = Natura2000HaieSettings

    RESULT_MATRIX = {
        "non_soumis_aa": RESULTS.non_soumis,
        "non_soumis": RESULTS.non_soumis,
        "soumis": RESULTS.soumis,
    }

    def get_catalog_data(self):
        """Let's compute the length of hedges crossing the N2000 perimeter."""

        hedges = self.catalog["haies"].hedges_to_remove()
        hors_alignement = [h for h in hedges if h.hedge_type != "alignement"]
        alignement = [h for h in hedges if h.hedge_type == "alignement"]

        hedges_geom = MultiLineString(
            [h.geos_geometry for h in hedges], srid=EPSG_WGS84
        )

        # Find all the Zones for the current Perimeter and that intersects any of the hedges
        qs = (
            self.moulinette.natura2000_haie.natura2000_haie.activation_map.zones.all()
            .filter(geometry__intersects=hedges_geom)
            .aggregate(geom=Union(Cast("geometry", MultiPolygonField())))
        )
        # Aggregate them into a single polygon
        multipolygon = qs["geom"]

        n2000_hors_aa = {}
        l_n2000_hors_aa = 0.0

        n2000_aa = {}
        l_n2000_aa = 0.0

        # Use the geodesic length
        geod = Geod(ellps="WGS84")

        # multipolygon is None if there is only hedges to plant that are intersecting the perimeter
        if multipolygon:
            # Other conversion options throw a cryptic numpy error, so…
            geom = shapely.from_wkt(multipolygon.wkt)
            # Intersect every hedge.
            for h in hors_alignement:
                intersect = h.geometry.intersection(geom)
                length = geod.geometry_length(intersect)
                if length > 0.0:
                    n2000_hors_aa[h.id] = ceil(length)
                    l_n2000_hors_aa += length

            for h in alignement:
                intersect = h.geometry.intersection(geom)
                length = geod.geometry_length(intersect)
                if length > 0.0:
                    n2000_aa[h.id] = ceil(length)
                    l_n2000_aa += length

        data = {}
        data["n2000_hors_aa"] = n2000_hors_aa
        data["l_n2000_hors_aa"] = ceil(l_n2000_hors_aa)
        data["n2000_aa"] = n2000_aa
        data["l_n2000_aa"] = ceil(l_n2000_aa)

        return data

    def get_result_data(self):
        """Returns if a non-alignement hedge intersects the n2000 zone.

        If we are evaluating this criterion, it means that *some* hedges have intersected
        a n2000 zone. But since some hedge types are excluded, we have to run a more
        specific check again.
        """

        return self.catalog["l_n2000_hors_aa"] > 0.0

    def get_result_code(self, intersects_n2000):
        if intersects_n2000:
            code = self.settings.get("result", "non_soumis")
        else:
            code = "non_soumis_aa"

        return code
