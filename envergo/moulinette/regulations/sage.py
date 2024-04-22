from django import forms

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, Map, MapPolygon
from envergo.moulinette.regulations.mixins import ZoneHumideMixin

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"
BLACK = "#000000"


class ZoneHumideVieJaunay85(ZoneHumideMixin, CriterionEvaluator):
    choice_label = "85 - Zone humide Vie & Jaunay"
    slug = "zone_humide_vie_jaunay_85"

    CODES = [
        "interdit",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "non_soumis",
    ]

    CODE_MATRIX = {
        ("inside", "big"): "interdit",
        ("inside", "medium"): "action_requise_interdit",
        ("inside", "small"): "non_soumis",
        ("close_to", "big"): "action_requise_proche_interdit",
        ("close_to", "medium"): "non_soumis",
        ("close_to", "small"): "non_soumis",
        ("outside", "big"): "non_soumis_dehors",
        ("outside", "medium"): "non_soumis_dehors",
        ("outside", "small"): "non_soumis_dehors",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "action_requise_interdit": RESULTS.action_requise,
        "action_requise_proche_interdit": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_dehors": RESULTS.non_soumis,
    }

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """

        if self.catalog["forbidden_wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["forbidden_wetlands_within_100m"]:
            wetland_status = "close_to"
        else:
            wetland_status = "outside"

        if self.catalog["created_surface"] >= 1000:
            project_size = "big"
        elif self.catalog["created_surface"] >= 700:
            project_size = "medium"
        else:
            project_size = "small"

        return wetland_status, project_size

    def get_map(self):
        map_polygons = []

        wetlands_qs = [
            zone
            for zone in self.catalog["forbidden_wetlands"]
            if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLACK, "Zone humide"))

        if self.catalog["forbidden_wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif self.catalog["forbidden_wetlands_within_100m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée."
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


class ZoneHumideGMRE56(ZoneHumideMixin, CriterionEvaluator):
    choice_label = "56 - Zone humide GMRE"
    slug = "zone_humide_gmre_56"

    CODES = [
        "interdit",
        "action_requise_proche_interdit",
        "action_requise_dans_doute_interdit",
        "non_soumis",
    ]

    CODE_MATRIX = {
        "inside": "interdit",
        "close_to": "action_requise_proche_interdit",
        "inside_potential": "action_requise_dans_doute_interdit",
        "outside": "non_soumis",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "action_requise_proche_interdit": RESULTS.action_requise,
        "action_requise_dans_doute_interdit": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
    }

    def get_result_data(self):
        """Evaluate the project and return the different parameter results."""

        if self.catalog["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["wetlands_within_100m"]:
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_10m"]:
            wetland_status = "inside_potential"
        else:
            wetland_status = "outside"

        return wetland_status

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
                center=self.catalog["coords"],
                entries=map_polygons,
                caption=caption,
                truncate=False,
            )
        else:
            criterion_map = None

        return criterion_map


class ImpactZHSettings(forms.Form):
    threshold = forms.IntegerField(
        label="Seuil d'impact (en m²)",
        help_text="Si le projet impacte plus de ce nombre de m² de zone humide, il sera interdit.",
    )
    exceptions = forms.CharField(
        label="Texte exceptions (html)",
        help_text="Indiquez la liste des exceptions mentionnées dans l'arrêté préfectoral d'interdiction.",
        required=False,
    )


class ImpactZoneHumide(ZoneHumideMixin, CriterionEvaluator):
    choice_label = "SAGE > Interdiction impact ZH"
    slug = "interdiction_impact_zh"
    settings_form_class = ImpactZHSettings
    zh_strict = False

    CODES = [
        "interdit",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "action_requise_dans_doute_interdit",
        "non_soumis",
        "non_soumis_dehors",
    ]

    CODE_MATRIX = {
        ("inside", "big"): "interdit",
        ("inside", "medium"): "action_requise_interdit",
        ("inside", "small"): "non_soumis",
        ("close_to", "big"): "action_requise_proche_interdit",
        ("close_to", "medium"): "non_soumis",
        ("close_to", "small"): "non_soumis",
        ("potential", "big"): "action_requise_dans_doute_interdit",
        ("potential", "medium"): "non_soumis",
        ("potential", "small"): "non_soumis",
        ("outside", "big"): "non_soumis_dehors",
        ("outside", "medium"): "non_soumis_dehors",
        ("outside", "small"): "non_soumis_dehors",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "action_requise_interdit": RESULTS.action_requise,
        "action_requise_proche_interdit": RESULTS.action_requise,
        "action_requise_dans_doute_interdit": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_dehors": RESULTS.non_soumis,
    }

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """
        settings_form = self.get_settings_form()
        settings_form.is_valid()

        if (
            self.catalog["wetlands_within_25m"]
            or self.catalog["forbidden_wetlands_within_25m"]
        ):
            wetland_status = "inside"
        elif (
            self.catalog["wetlands_within_100m"]
            or self.catalog["forbidden_wetlands_within_100m"]
        ):
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_10m"]:
            wetland_status = "potential"
        else:
            wetland_status = "outside"

        threshold = settings_form.cleaned_data["threshold"]
        # Special case: whenever the surface is zero, the project is "non soumis",
        # even if the threshold is also zero.
        if self.catalog["created_surface"] == 0:
            project_size = "small"
        elif self.catalog["created_surface"] >= threshold:
            project_size = "big"
        elif self.catalog["created_surface"] >= threshold * 0.7:
            project_size = "medium"
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

        forbidden_wetlands_qs = [
            zone
            for zone in self.catalog["forbidden_wetlands"]
            if zone.map.display_for_user
        ]
        if forbidden_wetlands_qs:
            map_polygons.append(MapPolygon(forbidden_wetlands_qs, BLUE, "Zone humide"))

        potential_qs = [
            zone
            for zone in self.catalog["potential_wetlands"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, LIGHTBLUE, "Zone humide potentielle")
            )

        if (
            self.catalog["wetlands_within_25m"]
            or self.catalog["forbidden_wetlands_within_25m"]
        ):
            caption = "Le projet se situe dans une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            or self.catalog["forbidden_wetlands_within_100m"]
        ) and not self.catalog["potential_wetlands_within_10m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            or self.catalog["forbidden_wetlands_within_100m"]
        ) and self.catalog["potential_wetlands_within_10m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
        elif self.catalog["potential_wetlands_within_10m"] and potential_qs:
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


class ImpactZoneHumideStrict(ZoneHumideMixin, CriterionEvaluator):
    choice_label = "SAGE > Interdiction impact ZH (carte stricte)"
    slug = "interdiction_impact_zh"
    settings_form_class = ImpactZHSettings
    zh_strict = True

    CODES = [
        "interdit",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "non_soumis",
        "non_soumis_dehors",
    ]

    CODE_MATRIX = {
        ("inside", "big"): "interdit",
        ("inside", "medium"): "action_requise_interdit",
        ("inside", "small"): "non_soumis",
        ("close_to", "big"): "action_requise_proche_interdit",
        ("close_to", "medium"): "non_soumis",
        ("close_to", "small"): "non_soumis",
        ("outside", "big"): "non_soumis_dehors",
        ("outside", "medium"): "non_soumis_dehors",
        ("outside", "small"): "non_soumis_dehors",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "action_requise_interdit": RESULTS.action_requise,
        "action_requise_proche_interdit": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_dehors": RESULTS.non_soumis,
    }

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """
        settings_form = self.get_settings_form()
        settings_form.is_valid()

        if self.catalog["forbidden_wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["forbidden_wetlands_within_100m"]:
            wetland_status = "close_to"
        else:
            wetland_status = "outside"

        threshold = settings_form.cleaned_data["threshold"]
        # Special case: whenever the surface is zero, the project is "non soumis",
        # even if the threshold is also zero.
        if self.catalog["created_surface"] == 0:
            project_size = "small"
        elif self.catalog["created_surface"] >= threshold:
            project_size = "big"
        elif self.catalog["created_surface"] >= threshold * 0.7:
            project_size = "medium"
        else:
            project_size = "small"

        return wetland_status, project_size

    def get_map(self):
        map_polygons = []

        wetlands_qs = [
            zone
            for zone in self.catalog["forbidden_wetlands"]
            if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLACK, "Zone humide"))

        if self.catalog["forbidden_wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif self.catalog["forbidden_wetlands_within_100m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée."
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


class ImpactZHIOTASettings(forms.Form):
    exceptions = forms.CharField(
        label="Texte exceptions (html)",
        help_text="Indiquez la liste des exceptions mentionnées dans l'arrêté préfectoral d'interdiction.",
        required=False,
    )


class ImpactZoneHumideIOTA(ZoneHumideMixin, CriterionEvaluator):
    choice_label = "SAGE > Interdiction impact ZH si IOTA"
    slug = "interdiction_impact_zh_iota"
    settings_form_class = ImpactZHIOTASettings
    zh_strict = False

    CODES = [
        "interdit",
        "a_verifier",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "action_requise_dans_doute_interdit",
        "non_soumis",
        "non_soumis_dehors",
    ]

    CODE_MATRIX = {
        ("inside", "soumis"): "interdit",
        ("inside", "action_requise"): "a_verifier",
        ("inside", "non_soumis"): "non_soumis",
        ("close_to", "soumis"): "action_requise_proche_interdit",
        ("close_to", "action_requise"): "action_requise_interdit",
        ("close_to", "non_soumis"): "non_soumis",
        ("potential", "soumis"): "action_requise_dans_doute_interdit",
        ("potential", "action_requise"): "action_requise_interdit",
        ("potential", "non_soumis"): "non_soumis",
        ("outside", "soumis"): "non_soumis_dehors",
        ("outside", "action_requise"): "non_soumis_dehors",
        ("outside", "non_soumis"): "non_soumis_dehors",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "a_verifier": RESULTS.a_verifier,
        "action_requise_interdit": RESULTS.action_requise,
        "action_requise_proche_interdit": RESULTS.action_requise,
        "action_requise_dans_doute_interdit": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_dehors": RESULTS.non_soumis,
    }

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """
        if (
            self.catalog["wetlands_within_25m"]
            or self.catalog["forbidden_wetlands_within_25m"]
        ):
            wetland_status = "inside"
        elif (
            self.catalog["wetlands_within_100m"]
            or self.catalog["forbidden_wetlands_within_100m"]
        ):
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_10m"]:
            wetland_status = "potential"
        else:
            wetland_status = "outside"

        iota_result = self.moulinette.loi_sur_leau.result

        return wetland_status, iota_result

    def get_map(self):
        map_polygons = []

        wetlands_qs = [
            zone for zone in self.catalog["wetlands"] if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLUE, "Zone humide"))

        forbidden_wetlands_qs = [
            zone
            for zone in self.catalog["forbidden_wetlands"]
            if zone.map.display_for_user
        ]
        if forbidden_wetlands_qs:
            map_polygons.append(MapPolygon(forbidden_wetlands_qs, BLUE, "Zone humide"))

        potential_qs = [
            zone
            for zone in self.catalog["potential_wetlands"]
            if zone.map.display_for_user
        ]
        if potential_qs:
            map_polygons.append(
                MapPolygon(potential_qs, LIGHTBLUE, "Zone humide potentielle")
            )

        if (
            self.catalog["wetlands_within_25m"]
            or self.catalog["forbidden_wetlands_within_25m"]
        ):
            caption = "Le projet se situe dans une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            or self.catalog["forbidden_wetlands_within_100m"]
        ) and not self.catalog["potential_wetlands_within_10m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée."

        elif (
            self.catalog["wetlands_within_100m"]
            or self.catalog["forbidden_wetlands_within_100m"]
        ) and self.catalog["potential_wetlands_within_10m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée et dans une zone humide potentielle."
        elif self.catalog["potential_wetlands_within_10m"] and potential_qs:
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


class ImpactZoneHumideIOTAStrict(ZoneHumideMixin, CriterionEvaluator):
    choice_label = "SAGE > Interdiction impact ZH si IOTA (carte stricte)"
    slug = "interdiction_impact_zh_iota"
    settings_form_class = ImpactZHIOTASettings
    zh_strict = True

    CODES = [
        "interdit",
        "a_verifier",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "non_soumis",
        "non_soumis_dehors",
    ]

    CODE_MATRIX = {
        ("inside", "soumis"): "interdit",
        ("inside", "action_requise"): "a_verifier",
        ("inside", "non_soumis"): "non_soumis",
        ("close_to", "soumis"): "action_requise_proche_interdit",
        ("close_to", "action_requise"): "action_requise_interdit",
        ("close_to", "non_soumis"): "non_soumis",
        ("outside", "soumis"): "non_soumis_dehors",
        ("outside", "action_requise"): "non_soumis_dehors",
        ("outside", "non_soumis"): "non_soumis_dehors",
    }

    RESULT_MATRIX = {
        "interdit": RESULTS.interdit,
        "a_verifier": RESULTS.a_verifier,
        "action_requise_interdit": RESULTS.action_requise,
        "action_requise_proche_interdit": RESULTS.action_requise,
        "non_soumis": RESULTS.non_soumis,
        "non_soumis_dehors": RESULTS.non_soumis,
    }

    def get_result_data(self):
        """Evaluate the project and return the different parameter results.

        For this criterion, the evaluation results depends on the project size
        and wether it will impact known wetlands.
        """
        if self.catalog["forbidden_wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["forbidden_wetlands_within_100m"]:
            wetland_status = "close_to"
        else:
            wetland_status = "outside"

        iota_result = self.moulinette.loi_sur_leau.result

        return wetland_status, iota_result

    def get_map(self):
        map_polygons = []

        wetlands_qs = [
            zone
            for zone in self.catalog["forbidden_wetlands"]
            if zone.map.display_for_user
        ]
        if wetlands_qs:
            map_polygons.append(MapPolygon(wetlands_qs, BLACK, "Zone humide"))

        if self.catalog["forbidden_wetlands_within_25m"]:
            caption = "Le projet se situe dans une zone humide référencée."

        elif self.catalog["forbidden_wetlands_within_100m"]:
            caption = "Le projet se situe à proximité d'une zone humide référencée."
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
