from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Exists, OuterRef
from shapely import MultiLineString

from envergo.evaluations.models import RESULTS
from envergo.geodata.models import Zone
from envergo.moulinette.regulations import CriterionEvaluator


class Natura2000HaieSettings(forms.Form):
    result = forms.ChoiceField(
        label="Resultat attendu de l'évaluateur",
        help_text="Indique si l’arrachage de haies est soumis à évaluation des incidences Natura 2000 pour ce critère.",
        required=True,
        choices=RESULTS,
    )


class Natura2000Haie(CriterionEvaluator):
    choice_label = "Natura 2000 > Haie"
    slug = "natura2000_haie"
    settings_form_class = Natura2000HaieSettings

    RESULT_MATRIX = {
        "non_soumis_aa": RESULTS.non_soumis,
        "non_soumis": RESULTS.non_soumis,
        "soumis": RESULTS.soumis,
    }

    def get_result_data(self):
        """Returns if a non-alignement hedge intersects the n2000 zone.

        If we are evaluating this criterion, it means that *some* hedges have intersected
        a n2000 zone. But since some hedge types are excluded, we have to run a more
        specific check again.
        """

        # We have to import here to prevent circular import error
        from envergo.moulinette.fields import classpath
        from envergo.moulinette.models import Criterion

        hedges_except_alignement = [
            h
            for h in self.catalog["haies"].hedges_to_remove()
            if h.hedge_type != "alignement"
        ]

        if len(hedges_except_alignement) == 0:
            # If we are here, it means all hedges are of type "alignement d'arbres"
            # which are not concerned by this criterion
            return False

        # Some non alignement hedges remain, we need to check if they intersect the
        # n2000 perimeter
        lines = [h.geometry for h in hedges_except_alignement]
        multiline = MultiLineString(lines)
        geometry = GEOSGeometry(multiline.wkb_hex)

        zone_subquery = (
            Zone.objects.filter(map_id=OuterRef("activation_map_id"))
            .filter(geometry__intersects=geometry)
            .values("id")
        )
        qs = Criterion.objects.filter(evaluator=classpath(self.__class__)).filter(
            Exists(zone_subquery)
        )
        return qs.exists()

    def get_result_code(self, intersects_n2000):
        if intersects_n2000:
            code = self.settings.get("result", "non_soumis")
        else:
            code = "non_soumis_aa"

        return code
