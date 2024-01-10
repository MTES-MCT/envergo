from django import forms
from django.contrib.gis.measure import Distance as D
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, Map, MapPolygon

BLUE = "blue"
LIGHTBLUE = "lightblue"


class ZoneHumide(CriterionEvaluator):
    choice_label = "Natura 2000 > Zone humide"
    slug = "zone_humide"

    CODES = [
        "soumis",
        "non_soumis",
        "action_requise_proche",
        "non_soumis_proche",
        "action_requise_dans_doute",
        "non_soumis_dans_doute",
        "non_concerne",
    ]

    CODE_MATRIX = {
        ("inside", "big"): "soumis",
        ("inside", "small"): "non_soumis",
        ("close_to", "big"): "action_requise_proche",
        ("close_to", "small"): "non_soumis_proche",
        ("inside_potential", "big"): "action_requise_dans_doute",
        ("inside_potential", "small"): "non_soumis_dans_doute",
        ("outside", "big"): "non_concerne",
        ("outside", "small"): "non_concerne",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "non_soumis": RESULTS.non_soumis,
        "action_requise_proche": RESULTS.action_requise,
        "non_soumis_proche": RESULTS.non_soumis,
        "action_requise_dans_doute": RESULTS.action_requise,
        "non_soumis_dans_doute": RESULTS.non_soumis,
        "non_concerne": RESULTS.non_concerne,
    }

    def get_catalog_data(self):
        data = super().get_catalog_data()

        if "wetlands_25" not in self.catalog:
            data["wetlands_25"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=25)
            ]
            data["wetlands_within_25m"] = bool(data["wetlands_25"])

        if "wetlands_100" not in self.catalog:
            data["wetlands_100"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=100)
            ]
            data["wetlands_within_100m"] = bool(data["wetlands_100"])

        if "potential_wetlands_0" not in self.catalog:
            data["potential_wetlands_0"] = [
                zone
                for zone in self.catalog["potential_wetlands"]
                if zone.distance <= D(m=0)
            ]
            data["potential_wetlands_within_0m"] = bool(data["potential_wetlands_0"])

        return data

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """

        if self.catalog["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["wetlands_within_100m"]:
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_0m"]:
            wetland_status = "inside_potential"
        else:
            wetland_status = "outside"

        if self.catalog["created_surface"] >= 100:
            project_size = "big"
        else:
            project_size = "small"

        return wetland_status, project_size

    def get_map(self):
        map_polygons = []

        wetlands_qs = [
            zone for zone in self.catalog["wetlands"] if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLUE, "Zone humide"))

        potential_qs = [
            zone
            for zone in self.catalog["potential_wetlands"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, LIGHTBLUE, "Zone humide potentielle")
            )

        if self.catalog["wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and not self.catalog["potential_wetlands_within_0m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and self.catalog["potential_wetlands_within_0m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
        elif self.catalog["potential_wetlands_within_0m"] and potential_qs:
            caption = "Le projet se situe dans une zone humide potentielle."
        else:
            caption = "Le projet ne se situe pas dans une zone humide référencée."

        if map_polygons:
            criterion_map = Map(
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


# Only for legacy purpose and not breaking existing data
class ZoneHumide44(ZoneHumide):
    choice_label = "Natura 2000 > 44 - Zone humide (obsolète)"


class ZoneInondable(CriterionEvaluator):
    choice_label = "Natura 2000 > Zone inondable"
    slug = "zone_inondable"

    CODES = ["soumis", "non_soumis", "non_concerne"]

    CODE_MATRIX = {
        ("inside", "big"): RESULTS.soumis,
        ("inside", "small"): RESULTS.non_soumis,
        ("outside", "big"): RESULTS.non_concerne,
        ("outside", "small"): RESULTS.non_concerne,
    }

    def get_catalog_data(self):
        data = super().get_catalog_data()

        if "flood_zones_12" not in self.catalog:
            data["flood_zones_12"] = [
                zone for zone in self.catalog["flood_zones"] if zone.distance <= D(m=12)
            ]
            data["flood_zones_within_12m"] = bool(data["flood_zones_12"])
        return data

    def get_result_data(self):
        if self.catalog["flood_zones_within_12m"]:
            flood_zone_status = "inside"
        else:
            flood_zone_status = "outside"

        if self.catalog["final_surface"] >= 200:
            project_size = "big"
        else:
            project_size = "small"

        return flood_zone_status, project_size

    def get_map(self):
        zone_qs = [
            zone for zone in self.catalog["flood_zones"] if zone.map.display_for_user
        ]

        if zone_qs:
            if self.catalog["flood_zones_within_12m"]:
                caption = "Le projet se situe dans une zone inondable."
            else:
                caption = "Le projet ne se situe pas en zone inondable."

            map_polygons = [MapPolygon(zone_qs, "red", "Zone inondable")]
            criterion_map = Map(
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class ZoneInondable44(ZoneInondable):
    choice_label = "Natura 2000 > 44 - Zone inondable (obsolète)"


class IOTA(CriterionEvaluator):
    choice_label = "Natura 2000 > IOTA"
    slug = "iota"

    CODES = ["soumis", "non_soumis", "iota_a_verifier"]

    def evaluate(self):
        try:
            iota = self.moulinette.loi_sur_leau.result
            if iota == RESULTS.soumis:
                result = RESULTS.soumis
            elif iota == RESULTS.non_soumis:
                result = RESULTS.non_soumis
            else:
                result = RESULTS.iota_a_verifier
        except AttributeError:
            # If there is no Loi sur l'eau regulation
            # for example, during unit tests
            result = RESULTS.non_disponible

        self._result_code, self._result = result, result


class LotissementForm(forms.Form):
    # I sacrificed a frog to the god of bad translations for the right to use
    # this variable name. Sorry.
    is_lotissement = forms.ChoiceField(
        label=_("Le projet concerne-t-il un lotissement ?"),
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )


class Lotissement(CriterionEvaluator):
    choice_label = "Natura 2000 > Lotissement"
    slug = "lotissement"
    form_class = LotissementForm

    CODES = [
        "soumis_dedans",
        "soumis_proximite_immediate",
        "non_soumis",
        "non_disponible",
    ]

    CODE_MATRIX = {
        ("oui", "dedans"): "soumis_dedans",
        ("oui", "proximite_immediate"): "soumis_proximite_immediate",
        ("non", "dedans"): "non_soumis",
        ("non", "proximite_immediate"): "non_soumis",
    }

    RESULT_MATRIX = {
        "soumis_dedans": RESULTS.soumis,
        "soumis_proximite_immediate": RESULTS.soumis,
        "non_soumis": RESULTS.non_soumis,
        "non_disponible": RESULTS.non_disponible,
    }

    def get_result_data(self):
        is_lotissement = self.catalog["is_lotissement"]
        if self.distance <= D(m=0.0):
            distance = "dedans"
        else:
            distance = "proximite_immediate"

        return is_lotissement, distance


AUTORISATION_URBA_CHOICES = (
    ("pa", "soumis à permis d'aménager (PA)"),
    ("pc", "soumis à permis de construire (PC)"),
    (
        "amenagement_dp",
        mark_safe(
            """
            un aménagement soumis à déclaration préalable (DP)
            <br /><span class='fr-hint-text'>au sens de l’art. R421-23
            du code de l’urbanisme</span>
        """
        ),
    ),
    (
        "construction_dp",
        mark_safe(
            """une construction soumise à déclaration préalable (DP)
            <br /><span class='fr-hint-text'>au sens de l’art. R421-9
            du code de l’urbanisme</span>
        """
        ),
    ),
    ("none", "soumis à aucune autorisation d'urbanisme"),
    ("other", "autre / je ne sais pas"),
)


class AutorisationUrbanismeForm(forms.Form):
    autorisation_urba = forms.ChoiceField(
        label="Le projet est-il…",
        widget=forms.RadioSelect,
        choices=AUTORISATION_URBA_CHOICES,
        required=True,
    )


class AutorisationUrbanisme(CriterionEvaluator):
    choice_label = "Natura 2000 > Autorisation urba"
    slug = "autorisation_urba"
    form_class = AutorisationUrbanismeForm

    CODES = ["soumis", "a_verifier", "non_soumis"]

    CODE_MATRIX = {
        "pa": "soumis",
        "pc": "soumis",
        "amenagement_dp": "soumis",
        "construction_dp": "soumis",
        "none": "non_soumis",
        "other": "a_verifier",
    }

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "a_verifier": RESULTS.a_verifier,
        "non_soumis": RESULTS.non_soumis,
    }

    def get_result_data(self):
        autorisation_urba = self.catalog["autorisation_urba"]
        return autorisation_urba

    def get_result_code(self, result_data):
        """For this criterion, the result will depend on the department."""

        # Get custom `data to result code` matrix from moulinette config
        config = self.moulinette.config
        urba_code_matrix = config.n2000_autorisation_urba_result
        try:
            result_code = urba_code_matrix[result_data]
            if result_code not in self.RESULT_MATRIX.keys():
                raise ValueError
        except (KeyError, ValueError):
            result_code = super().get_result_code(result_data)

        return result_code


class AutorisationUrbanismeExcLotissementForm(
    LotissementForm, AutorisationUrbanismeForm
):
    pass


class AutorisationUrbanismeExcLotissement(AutorisationUrbanisme):
    """Custom evaluator with a special rule that only applies in some depts.

    In some departments (91 & 77 right now), this special rule applies:
    « Tous les projets soumis à PA sont soumis à EIN sauf la catégorie la plus
    fréquente et la plus impactante : les lotissements. »

    This is a weird rule, but that's life.

    In addition to the question 'Is the project subject to autorisation d'urabanisme,'
    it is necessary to ask the supplementary question 'Is the project a lotissement?'
    """

    choice_label = "Natura 2000 > Autorisation urba (exception lotissement)"
    form_class = AutorisationUrbanismeExcLotissementForm

    def get_result_data(self):
        autorisation_urba = self.catalog["autorisation_urba"]
        is_lotissement = self.catalog["is_lotissement"]
        return autorisation_urba, is_lotissement

    def get_result_code(self, result_data):
        """For this criterion, the result will depend on the department."""

        # Check for the exception case
        autorisation_urba, is_lotissement = result_data
        if autorisation_urba == "pa" and is_lotissement == "oui":
            result_code = "non_soumis"
        else:
            result_code = super().get_result_code(autorisation_urba)

        return result_code
