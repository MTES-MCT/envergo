from math import ceil

import shapely
from django import forms
from django.contrib.gis.db.models import MultiPolygonField
from django.contrib.gis.db.models.aggregates import Union
from django.contrib.gis.geos import MultiLineString
from django.db.models.functions import Cast
from pyproj import Geod

from envergo.moulinette.regulations import CriterionEvaluator, HaieRegulationEvaluator


class ReservesNaturellesRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Réserves naturelles"

    PROCEDURE_TYPE_MATRIX = {
        "soumis_autorisation": "autorisation",
        "soumis_declaration": "declaration",
        "non_concerne": "declaration",
    }


class ReservesNaturellesForm(forms.Form):
    plan_gestion = forms.ChoiceField(
        label="La destruction de haies est-elle prévue dans le plan de gestion de la réserve naturelle où elle se "
        "situe ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )


EPSG_WGS84 = 4326
EPSG_LAMB93 = 2154


class ReservesNaturelles(CriterionEvaluator):
    choice_label = "Réserves naturelles > Réserves naturelles"
    slug = "reserves_naturelles"
    form_class = ReservesNaturellesForm

    CODE_MATRIX = {
        "oui": "soumis_declaration",
        "non": "soumis_autorisation",
    }

    def get_catalog_data(self):
        """Compute the length of hedges to remove in reserve naturelle"""

        catalog = super().get_catalog_data()
        hedges_to_remove = self.catalog["haies"].hedges_to_remove()

        # Make sure those variable always exist
        resnat = {}
        l_resnat = 0.0

        if hedges_to_remove:
            hedges_geom = MultiLineString(
                [h.geos_geometry for h in hedges_to_remove], srid=EPSG_WGS84
            )

            # Find all the Zones for the current Perimeter and that intersects any of the hedges
            qs = (
                self.moulinette.reserves_naturelles.reserves_naturelles.activation_map.zones.all()
                .filter(geometry__intersects=hedges_geom)
                .aggregate(geom=Union(Cast("geometry", MultiPolygonField())))
            )
            # Aggregate them into a single polygon.
            # Union returns None when no zones match the filter.
            multipolygon = qs["geom"]

            if multipolygon is not None:
                # Other conversion options throw a cryptic numpy error, so…
                geom = shapely.from_wkt(multipolygon.wkt)

                # Use the geodesic length
                geod = Geod(ellps="WGS84")

                for h in hedges_to_remove:
                    intersect = h.geometry.intersection(geom)
                    length = geod.geometry_length(intersect)
                    if length > 0.0:
                        resnat[h.id] = ceil(length)
                        l_resnat += length

        catalog["resnat"] = resnat
        catalog["l_resnat"] = ceil(l_resnat)

        return catalog

    def get_result_data(self):
        plan_gestion = self.catalog["plan_gestion"]
        return plan_gestion
