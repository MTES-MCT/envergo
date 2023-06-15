from functools import cached_property

from django.contrib.gis.measure import Distance as D

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import (
    Map,
    MapPolygon,
    MoulinetteCriterion,
    MoulinetteRegulation,
    RequiredAction,
    Stake,
)

BLUE = "#0000FF"
LIGHTBLUE = "#00BFFF"
BLACK = "#000000"


class ZoneHumideVieJaunay85(MoulinetteCriterion):
    slug = "zone_humide_vie_jaunay_85"
    choice_label = "85 - Zone humide Vie & Jaunay"
    title = "Impact sur une zone humide"
    subtitle = "Seuil d'interdiction : 1 000 m²"
    header = "Article 5 du <a target='_blank' rel='noopener' href='https://www.gesteau.fr/document/reglement-du-sage-de-la-vie-et-du-jaunay'>règlement du SAGE Vie et Jaunay</a>"  # noqa

    CODES = [
        "interdit",
        "action_requise_interdit",
        "action_requise_proche_interdit",
        "non_soumis",
        "non_concerne",
    ]

    def get_catalog_data(self):
        data = {}
        wetlands = self.catalog["forbidden_wetlands"]

        if "forbidden_wetlands_25" not in data:
            data["forbidden_wetlands_25"] = [
                zone for zone in wetlands if zone.distance <= D(m=25)
            ]
            data["forbidden_wetlands_within_25m"] = bool(data["forbidden_wetlands_25"])

        if "forbidden_wetlands_100" not in data:
            data["forbidden_wetlands_100"] = [
                zone for zone in wetlands if zone.distance <= D(m=100)
            ]
            data["forbidden_wetlands_within_100m"] = bool(
                data["forbidden_wetlands_100"]
            )

        return data

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

    @property
    def result_code(self):
        """Return the unique result code."""

        wetland_status, project_size = self.get_result_data()
        code_matrix = {
            ("inside", "big"): "interdit",
            ("inside", "medium"): "action_requise_interdit",
            ("inside", "small"): "non_soumis",
            ("close_to", "big"): "action_requise_proche_interdit",
            ("close_to", "medium"): "non_soumis",
            ("close_to", "small"): "non_soumis",
            ("outside", "big"): "non_concerne",
            ("outside", "medium"): "non_concerne",
            ("outside", "small"): "non_concerne",
        }
        code = code_matrix[(wetland_status, project_size)]
        return code

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "interdit": RESULTS.interdit,
            "action_requise_interdit": RESULTS.action_requise,
            "action_requise_proche_interdit": RESULTS.action_requise,
            "non_soumis": RESULTS.non_soumis,
            "non_concerne": RESULTS.non_concerne,
        }
        result = result_matrix[code]
        return result

    def _get_map(self):
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
                zoom=18,
            )
        else:
            criterion_map = None

        return criterion_map

    def required_action(self):
        action = None
        if self.result == RESULTS.action_requise:
            action = RequiredAction(
                stake=Stake.INTERDIT,
                text="n’impacte pas plus 1 000 m² de zone humide référencée dans le règlement du SAGE Vie et Jaunay",
            )
        return action

    def project_impact(self):
        impact = None
        if self.result == RESULTS.interdit:
            impact = """
                impacte plus de 1 000 m² de l’une des zones humides référencées
                dans le règlement du SAGE Vie et Jaunay.
            """
        return impact

    def discussion_contact(self):
        contact = None
        if self.result in (RESULTS.action_requise, RESULTS.interdit):
            contact = """
            de la structure en charge de l’animation du SAGE Vie et Jaunay :
            <div class="fr-highlight fr-mb-2w fr-ml-0 fr-mt-1w">
                <address>
                <strong>Syndicat Mixte des Marais, de la Vie, du Ligneron et du Jaunay</strong><br />
                Téléphone : 02 51 54 28 18<br />
                Site internet : <a href="https://www.vie-jaunay.com" target="_blank" rel="noopener">vie-jaunay.com</a>
                </address>
            </div>
            """
        return contact


class ZoneHumideGMRE56(MoulinetteCriterion):
    slug = "zone_humide_gmre_56"
    choice_label = "56 - Zone humide GMRE"
    title = "Impact sur une zone humide"
    subtitle = "Seuil d'interdiction : dès le premier m²"
    header = "Règle 4 du <a target='_blank' rel='noopener' href='https://www.gesteau.fr/document/sage-golfe-du-morbihan-et-ria-detel-reglement'>règlement du SAGE Golfe du Morbihan & Ria d’Etel</a>"  # noqa

    CODES = [
        "interdit",
        "action_requise_proche_interdit",
        "action_requise_dans_doute_interdit",
        "non_concerne",
    ]

    def get_catalog_data(self):
        data = {}

        if "wetlands_25" not in data:
            data["wetlands_25"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=25)
            ]
            data["wetlands_within_25m"] = bool(data["wetlands_25"])

        if "wetlands_100" not in data:
            data["wetlands_100"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=100)
            ]
            data["wetlands_within_100m"] = bool(data["wetlands_100"])

        if "potential_wetlands_0" not in data:
            data["potential_wetlands_0"] = [
                zone
                for zone in self.catalog["potential_wetlands"]
                if zone.distance <= D(m=0)
            ]
            data["potential_wetlands_within_0m"] = bool(data["potential_wetlands_0"])

        return data

    def get_result_data(self):
        """Evaluate the project and return the different parameter results."""

        if self.catalog["wetlands_within_25m"]:
            wetland_status = "inside"
        elif self.catalog["wetlands_within_100m"]:
            wetland_status = "close_to"
        elif self.catalog["potential_wetlands_within_0m"]:
            wetland_status = "inside_potential"
        else:
            wetland_status = "outside"

        return wetland_status

    @property
    def result_code(self):
        """Return the unique result code."""

        wetland_status = self.get_result_data()
        results = {
            "inside": "interdit",
            "close_to": "action_requise_proche_interdit",
            "inside_potential": "action_requise_dans_doute_interdit",
            "outside": "non_concerne",
        }
        code = results[wetland_status]
        return code

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "interdit": RESULTS.interdit,
            "action_requise_proche_interdit": RESULTS.action_requise,
            "action_requise_dans_doute_interdit": RESULTS.action_requise,
            "non_concerne": RESULTS.non_concerne,
        }
        result = result_matrix[code]
        return result

    def _get_map(self):
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
                zoom=18,
            )
        else:
            criterion_map = None

        return criterion_map

    def required_action(self):
        action = None
        if self.result == RESULTS.action_requise:
            action = RequiredAction(
                stake=Stake.INTERDIT,
                text="n’impacte aucun m² de zone humide",
            )
        return action

    def project_impact(self):
        impact = None
        if self.result == RESULTS.interdit:
            impact = "impacte une zone humide dans le périmètre du SAGE Golfe du Morbihan & Ria d'Etel."
        return impact

    def discussion_contact(self):
        contact = None
        if self.result in (RESULTS.action_requise, RESULTS.interdit):
            contact = """
            de la structure en charge de l’animation du SAGE Golfe du Morbihan et Ria d'Etel :
            <div class="fr-highlight fr-mb-2w fr-ml-0 fr-mt-1w">
                <address>
                <strong>Syndicat Mixte du SAGE Golfe du Morbihan et Ria d’Etel</strong><br />
                Téléphone : 02 97 52 47 60<br />
                Site internet : <a href="https://www.sagegmre.fr/contact,pa12.html" target="_blank" rel="noopener">
                https://www.sagegmre.fr</a>
                </address>
            </div>
            """
        return contact


class Sage(MoulinetteRegulation):
    slug = "sage"
    title = "Règlement de SAGE"
    criterion_classes = [ZoneHumideVieJaunay85, ZoneHumideGMRE56]

    @cached_property
    def result(self):
        """Compute global result from individual criterions."""

        results = [criterion.result for criterion in self.criterions]

        if RESULTS.interdit in results:
            result = RESULTS.interdit
        elif RESULTS.action_requise in results:
            result = RESULTS.action_requise
        elif RESULTS.non_soumis in results:
            result = RESULTS.non_soumis
        else:
            result = RESULTS.non_disponible

        return result
