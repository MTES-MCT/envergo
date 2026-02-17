from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms.fields import DisplayChoiceField
from envergo.moulinette.regulations import (
    TO_ADD,
    ActionsToTakeMixin,
    AmenagementRegulationEvaluator,
    CriterionEvaluator,
    Map,
    MapPolygon,
    SelfDeclarationMixin,
)
from envergo.moulinette.regulations.mixins import ZoneHumideMixin, ZoneInondableMixin

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"


class Natura2000Regulation(ActionsToTakeMixin, AmenagementRegulationEvaluator):
    choice_label = "Aménagement > Natura 2000"

    ACTIONS_TO_TAKE_MATRIX = {"soumis": {TO_ADD: {"depot_ein", "pc_ein"}}}


class ZoneHumideSettingsForm(forms.Form):
    threshold = forms.fields.IntegerField(
        label="Seuil réglementaire (en m²)",
        help_text="Seuil à partir duquel le critère est applicable (généralement 100m²).",
        required=True,
    )


class ZoneHumide(
    ZoneHumideMixin,
    SelfDeclarationMixin,
    ActionsToTakeMixin,
    CriterionEvaluator,
):
    choice_label = "Natura 2000 > Zone humide"
    slug = "zone_humide"
    settings_form_class = ZoneHumideSettingsForm

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

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": {TO_ADD: {"etude_zh_n2000"}}}

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """

        if self.catalog["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["wetlands_within_100m"]:
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_10m"]:
            wetland_status = "inside_potential"
        else:
            wetland_status = "outside"

        if self.catalog["created_surface"] >= self.settings.get("threshold"):
            project_size = "big"
        else:
            project_size = "small"

        return wetland_status, project_size

    def get_map(self):
        map_polygons = []

        potential_qs = [
            zone
            for zone in self.catalog["potential_wetlands"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, LIGHTBLUE, "Zone humide potentielle")
            )

        wetlands_qs = [
            zone for zone in self.catalog["wetlands"] if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLUE, "Zone humide"))

        if self.catalog["wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and not self.catalog["potential_wetlands_within_10m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            and self.catalog["potential_wetlands_within_10m"]
        ):
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
        elif self.catalog["potential_wetlands_within_10m"] and potential_qs:
            caption = "Le projet se situe dans une zone humide potentielle."
        else:
            caption = "Le projet ne se situe pas dans une zone humide référencée."

        if map_polygons:
            criterion_map = Map(
                center=self.catalog["lng_lat"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class ZoneInondable(
    ZoneInondableMixin,
    SelfDeclarationMixin,
    ActionsToTakeMixin,
    CriterionEvaluator,
):
    choice_label = "Natura 2000 > Zone inondable"
    slug = "zone_inondable"

    CODES = ["soumis", "non_soumis", "non_concerne"]

    CODE_MATRIX = {
        ("inside", "big"): RESULTS.soumis,
        ("inside", "small"): RESULTS.non_soumis,
        ("outside", "big"): RESULTS.non_concerne,
        ("outside", "small"): RESULTS.non_concerne,
    }

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": {TO_ADD: {"etude_zi_n2000"}}}

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
                center=self.catalog["lng_lat"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class IOTA(SelfDeclarationMixin, CriterionEvaluator):
    choice_label = "Natura 2000 > IOTA"
    slug = "iota"

    CODES = ["soumis", "non_soumis", "iota_a_verifier"]

    def evaluate(self):
        try:
            iota = self.moulinette.loi_sur_leau.result
            if iota == RESULTS.soumis:
                result = RESULTS.soumis
            elif iota in (RESULTS.non_soumis, RESULTS.soumis_ou_pac):
                result = RESULTS.non_soumis
            else:
                result = RESULTS.iota_a_verifier
        except AttributeError:
            # If there is no Loi sur l'eau regulation
            # for example, during unit tests
            result = RESULTS.non_disponible

        self._result_code, self._result = result, result


class EvalEnv(SelfDeclarationMixin, CriterionEvaluator):
    choice_label = "Natura 2000 > EE"
    slug = "eval_env"

    def evaluate(self):
        try:
            evalenv = self.moulinette.eval_env.result
            if evalenv == RESULTS.cas_par_cas:
                result = ("soumis_cas_par_cas", RESULTS.soumis)
            elif evalenv == RESULTS.systematique:
                result = ("soumis_systematique", RESULTS.soumis)
            elif evalenv == RESULTS.non_soumis:
                result = (RESULTS.non_soumis, RESULTS.non_soumis)
            else:
                result = (RESULTS.non_disponible, RESULTS.non_disponible)
        except AttributeError:
            # If there is no Loi sur l'eau regulation
            # for example, during unit tests
            result = (RESULTS.non_disponible, RESULTS.non_disponible)

        self._result_code, self._result = result


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
    autorisation_urba = DisplayChoiceField(
        label="Le projet est-il…",
        widget=forms.RadioSelect,
        choices=AUTORISATION_URBA_CHOICES,
        required=True,
        display_label="Autorisation d'urbanisme :",
        get_display_value=lambda value: (
            "Non soumis"
            if value == "none"
            else dict(AUTORISATION_URBA_CHOICES).get(value, value)
        ),
    )


class AutorisationUrbanismeSettingsForm(forms.Form):
    result_code_matrix = forms.fields.JSONField(
        label="Codes de résultat (JSON)",
        help_text="Résultat du critère en fonction de la valeur d'autorisation urba",
        required=True,
    )


class AutorisationUrbanisme(SelfDeclarationMixin, CriterionEvaluator):
    choice_label = "Natura 2000 > Autorisation urba"
    slug = "autorisation_urba"
    form_class = AutorisationUrbanismeForm
    settings_form_class = AutorisationUrbanismeSettingsForm

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

        # Get custom `data to result code` matrix from settings form
        settings_form = self.get_settings_form()
        settings_form.is_valid()
        urba_code_matrix = settings_form.cleaned_data.get("result_code_matrix", {})
        try:
            result_code = urba_code_matrix[result_data]
            if result_code not in self.RESULT_MATRIX.keys():
                raise ValueError
        except (TypeError, KeyError, ValueError):
            result_code = super().get_result_code(result_data)

        return result_code


class LotissementForm(forms.Form):
    # I sacrificed a frog to the god of bad translations for the right to use
    # this variable name. Sorry.
    is_lotissement = forms.ChoiceField(
        label=_("Le projet concerne-t-il un lotissement ?"),
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )


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

    CODES = ["soumis", "a_verifier", "non_soumis", "non_soumis_lotissement"]

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "a_verifier": RESULTS.a_verifier,
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_lotissement": RESULTS.non_soumis,
    }

    def get_result_data(self):
        autorisation_urba = self.catalog["autorisation_urba"]
        is_lotissement = self.catalog["is_lotissement"]
        return autorisation_urba, is_lotissement

    def get_result_code(self, result_data):
        """For this criterion, the result will depend on the department."""

        # Check for the exception case
        autorisation_urba, is_lotissement = result_data
        if autorisation_urba == "pa" and is_lotissement == "oui":
            result_code = "non_soumis_lotissement"
        else:
            result_code = super().get_result_code(autorisation_urba)

        return result_code
