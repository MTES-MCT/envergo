from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from math import ceil, isclose

from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import TO_PLANT, TO_REMOVE


class PlantationCondition(ABC):
    """Evaluator for a single plantation condition."""

    label: str
    result: bool
    order: int = 0
    context: dict = dict()
    valid_text: str = "Condition validée"
    invalid_text: str = "Condition non validée"
    hint_text: str = ""

    # We want to display the raw class in the debug template, so we need to
    # prevent the template engine to instanciate the class
    do_not_call_in_templates = True

    def __init__(self, hedge_data, R, criterion_evaluator, catalog=None):
        self.hedge_data = hedge_data
        self.R = R
        self.catalog = catalog or {}
        self.criterion_evaluator = criterion_evaluator

    def must_display(self):
        """Should the condition be displayed?

        It does not make any sense to display the condition if it is related to a
        minimal length to plant and the length to plant is 0.
        """
        return True

    @abstractmethod
    def evaluate(self):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.evaluate` method."
        )

    @property
    def text(self):
        t = self.valid_text if self.result else self.invalid_text
        return mark_safe(t % self.context)

    @property
    def hint(self):
        return mark_safe(self.hint_text % self.context)


class MinLengthCondition(PlantationCondition):
    """Evaluate if there is enough hedges to plant in the project"""

    label = "Longueur de la haie plantée"
    order = 0
    valid_text = "Le linéaire total planté est suffisant."
    invalid_text = """
    Le linéaire total planté doit être supérieur à %(length_to_check)s m.<br />
    Il manque au moins %(left_to_plant)s m.
    """

    def evaluate(self):
        length_to_plant = self.hedge_data.length_to_plant()
        length_to_remove = self.hedge_data.length_to_remove()

        # Depending on the cases, we want to use the "classic" minimum length to
        # plant, or the "reduced" version (for Normandie rules)
        minimum_length_to_plant = length_to_remove * self.R
        length_to_check = minimum_length_to_plant
        if "reduced_lpm" in self.catalog and "aggregated_r" in self.catalog:
            if isclose(self.R, self.catalog["aggregated_r"]):
                length_to_check = self.catalog["reduced_lpm"]

        self.result = length_to_plant >= length_to_check

        left_to_plant = max(0, length_to_check - length_to_plant)
        self.context = {
            "R": self.R,
            "length_to_plant": round(length_to_plant),
            "length_to_remove": round(length_to_remove),
            "minimum_length_to_plant": ceil(minimum_length_to_plant),
            "left_to_plant": ceil(left_to_plant),
            "length_to_check": ceil(length_to_check),
        }

        if round(length_to_check) < round(minimum_length_to_plant):
            self.context["reduced_minimum_length_to_plant"] = ceil(length_to_check)
        return self

    def must_display(self):
        return self.context["length_to_check"] > 0


class MinLengthPacCondition(PlantationCondition):

    label = "Maintien des haies PAC"
    order = 1
    valid_text = "Le linéaire de haie planté sur parcelle PAC est suffisant."
    invalid_text = """
        Le linéaire de haie planté sur parcelle PAC doit être supérieur à %(minimum_length_to_plant_pac)s m.
        <br />
        Il manque au moins %(left_to_plant_pac)s m sur parcelle PAC, hors alignements d’arbres.
    """

    def evaluate(self):
        # For pac regulations, R is ignored unless it is zero
        R = 1 if self.R > 0 else 0
        length_to_plant = self.hedge_data.length_to_plant_pac()
        minimum_length_to_plant = self.hedge_data.lineaire_detruit_pac() * R
        self.result = length_to_plant >= minimum_length_to_plant

        left_to_plant = max(0, minimum_length_to_plant - length_to_plant)
        self.context = {
            "minimum_length_to_plant_pac": ceil(minimum_length_to_plant),
            "left_to_plant_pac": ceil(left_to_plant),
        }
        return self

    def must_display(self):
        return self.context["minimum_length_to_plant_pac"] > 0


class QualityCondition(PlantationCondition):
    label = "Type de haie plantée"
    order = 2
    valid_text = "Le type de haie plantée convient."
    invalid_text = """
      Le type de haie plantée n'est pas adapté au vu de celui des haies détruites.
    """

    def evaluate(self):
        """Evaluate the quality of the plantation project.
        The quality of the hedge planted must be at least as good as that of the hedge destroyed:
            Type 5 (mixte) hedges must be replaced by type 5 (mixte) hedges
            Type 4 (alignement) hedges must be replaced by type 4 (alignement) or 5 (mixte) hedges.
            Type 3 (arbustive) hedges must be replaced by type 3 (arbustive) hedges.
            Type 2 (buissonnante) hedges must be replaced by type 2 (buissonnante) or 3 (arbustive) hedges.
            Type 1 (degradee) hedges must be replaced by type 2 (buissonnante), 3 (arbustive) or 5 (mixte) hedges.

        return: {
            is_quality_sufficient: True if the plantation quality is sufficient, False otherwise,
            missing_plantation: {
                mixte: missing length of mixte hedges to plant,
                alignement: missing length of alignement hedges to plant,
                arbustive: missing length of arbustive hedges to plant,
                buissonante: missing length of buissonante hedges to plant,
                degradee: missing length of dégradée hedges to plant,
            }
        }
        """
        minimum_lengths_to_plant = self.get_minimum_lengths_to_plant()
        lengths_to_plant = self.get_lengths_to_plant()

        reliquat = {
            "mixte_remplacement_alignement": max(
                0, lengths_to_plant["mixte"] - minimum_lengths_to_plant["mixte"]
            ),
            "mixte_remplacement_dégradée": max(
                0,
                max(0, lengths_to_plant["mixte"] - minimum_lengths_to_plant["mixte"])
                - max(
                    0,
                    minimum_lengths_to_plant["alignement"]
                    - lengths_to_plant["alignement"],
                ),
            ),
            "arbustive_remplacement_buissonnante": max(
                0, lengths_to_plant["arbustive"] - minimum_lengths_to_plant["arbustive"]
            ),
            "arbustive_remplacement_dégradée": max(
                0,
                max(
                    0,
                    lengths_to_plant["arbustive"]
                    - minimum_lengths_to_plant["arbustive"],
                )
                - max(
                    0,
                    minimum_lengths_to_plant["buissonnante"]
                    - lengths_to_plant["buissonnante"],
                ),
            ),
            "buissonnante_remplacement_dégradée": max(
                0,
                lengths_to_plant["buissonnante"]
                - minimum_lengths_to_plant["buissonnante"],
            ),
        }

        missing_plantation = {
            "mixte": max(
                0, minimum_lengths_to_plant["mixte"] - lengths_to_plant["mixte"]
            ),
            "alignement": max(
                0,
                minimum_lengths_to_plant["alignement"]
                - lengths_to_plant["alignement"]
                - reliquat["mixte_remplacement_alignement"],
            ),
            "arbustive": max(
                0, minimum_lengths_to_plant["arbustive"] - lengths_to_plant["arbustive"]
            ),
            "buissonante": max(
                0,
                minimum_lengths_to_plant["buissonnante"]
                - lengths_to_plant["buissonnante"]
                - reliquat["arbustive_remplacement_buissonnante"],
            ),
            "degradee": max(
                0,
                minimum_lengths_to_plant["degradee"]
                - reliquat["mixte_remplacement_dégradée"]
                - reliquat["arbustive_remplacement_dégradée"]
                - reliquat["buissonnante_remplacement_dégradée"],
            ),
        }
        total_missing = sum(missing_plantation.values())
        self.result = total_missing == 0
        self.context = {
            "missing_plantation": missing_plantation,
        }
        return self

    def get_minimum_lengths_to_plant(self):
        lengths_by_type = defaultdict(int)
        for to_remove in self.hedge_data.hedges_to_remove():
            lengths_by_type[to_remove.hedge_type] += to_remove.length

        return {
            "degradee": self.R * lengths_by_type["degradee"],
            "buissonnante": self.R * lengths_by_type["buissonnante"],
            "arbustive": self.R * lengths_by_type["arbustive"],
            "mixte": self.R * lengths_by_type["mixte"],
            "alignement": self.R * lengths_by_type["alignement"],
        }

    def get_lengths_to_plant(self):
        lengths_by_type = defaultdict(int)
        for to_plant in self.hedge_data.hedges_to_plant():
            lengths_by_type[to_plant.hedge_type] += to_plant.length

        return {
            "buissonnante": lengths_by_type["buissonnante"],
            "arbustive": lengths_by_type["arbustive"],
            "mixte": lengths_by_type["mixte"],
            "alignement": lengths_by_type["alignement"],
        }

    def must_display(self):
        lengths = self.get_minimum_lengths_to_plant()
        sum_lengths = sum(lengths.values())
        return sum_lengths > 0

    @property
    def text(self):
        """Return the text to display for the condition."""
        if self.result:
            t = [self.valid_text]
        else:
            missing_plantation = self.context["missing_plantation"]
            t = [
                "Le type de haie plantée ne permet pas de compenser la qualité écologique des haies détruites."
            ]

            if missing_plantation["alignement"] > 0:
                t.append(
                    f"""
                    Il manque au moins {ceil(missing_plantation['mixte'] + missing_plantation['alignement'])} m
                    de haie mixte ou alignement d'arbres.
                    """
                )

            if missing_plantation["mixte"] > 0 or missing_plantation["degradee"] > 0:
                t.append(
                    f"""
                    Il manque au moins {ceil(missing_plantation['mixte'] + missing_plantation['degradee'])} m
                    de haie mixte.
                """
                )

            if missing_plantation["buissonante"] > 0:
                t.append(
                    f"""
                    Il manque au moins {ceil(missing_plantation['buissonante'] + missing_plantation['arbustive'])} m
                    de haie basse ou arbustive.
                """
                )

            if missing_plantation["arbustive"] > 0:
                t.append(
                    f"""
                    Il manque au moins {ceil(missing_plantation['arbustive'])} m de haie arbustive.
                """
                )

        return mark_safe("<br />\n".join(t))


HEDGE_KEYS = OrderedDict(
    [
        ("mixte", "Type 5 (mixte)"),
        ("alignement", "Type 4 (alignement)"),
        ("arbustive", "Type 3 (arbustive)"),
        ("buissonnante", "Type 2 (buissonnante)"),
        ("degradee", "Type 1 (dégradée)"),
    ]
)


class NormandieQualityCondition(PlantationCondition):
    label = "Type de haie plantée"
    order = 2
    valid_text = "Le type de haie plantée convient."
    invalid_text = """
      Le type de haie plantée n'est pas adapté au vu de celui des haies détruites.
    """

    # Hedge of type on the left can be replaced by the types on the right
    compensations = {
        "mixte": ["mixte"],
        "alignement": ["alignement", "mixte"],
        "arbustive": ["arbustive", "mixte"],
        "buissonnante": ["buissonnante", "arbustive", "mixte"],
        "degradee": ["buissonnante", "arbustive", "mixte"],
    }

    def evaluate(self):
        LC = self.catalog["LC"].copy()  # linéaire à compenser
        LP = defaultdict(int)  # linéaire à planter

        LPm = LC.copy()

        # Les haies à planter
        for hedge in self.hedge_data.hedges_to_plant():
            LP[hedge.hedge_type] += hedge.length

        LP_origin = LP.copy()

        # On calcule l'application des compensations
        # Pour chaque linéaire à compenser, on réparti les linéaires à planter
        # en fonction des substitutions possibles.

        for hedge_type in HEDGE_KEYS.keys():
            for compensation_type in self.compensations[hedge_type]:

                # Si on compense avec un type de qualité supérieur, le taux
                # de compensation est réduit de 20%
                rate = 1.0 if compensation_type == hedge_type else 0.8

                # Note: planter de la buissonnante n'est pas considéré comme une
                # amélioration de la dégradée, car il n'est pas possible de planter
                # de la dégradée.
                if hedge_type == "degradee" and compensation_type == "buissonnante":
                    rate = 1.0

                # Le linéaire planté vient réduire le linéaire à compenser
                compensation = min(LC[hedge_type], LP[compensation_type] / rate)
                LC[hedge_type] -= compensation
                LP[compensation_type] -= compensation * rate

        # À la fin, le linéaire à compenser doit être nul
        remaining_lc = sum(LC.values())
        self.result = remaining_lc == 0

        if (
            self.criterion_evaluator.result_code == "dispense_L350"
            or self.criterion_evaluator.result_code == "a_verifier_L350"
        ):
            # If the EP Normandie result code is "dispense_L350" or "a_verifier_L350,
            # we consider that the condition is always valid.
            self.result = True

        self.context["lpm"] = ceil(self.catalog["lpm"])
        self.context["reduced_lpm"] = ceil(self.catalog["reduced_lpm"])
        self.context["LC"] = LC
        self.context["LP"] = LP_origin
        self.context["LPm"] = LPm
        self.context["lm"] = remaining_lc
        self.context["lp"] = sum(LP_origin.values())

        return self

    @property
    def text(self):
        if self.result:
            t = self.valid_text
        else:
            lines = [self.invalid_text]

            LC = self.context["LC"]

            if LC["mixte"] > 0.0:
                lines.append(f"Il manque au moins {ceil(LC["mixte"])} m de haie mixte.")

            if LC["alignement"] > 0.0:
                lines.append(
                    f"Il manque au moins {ceil(LC["alignement"])} m de haie mixte ou d'alignement d'arbres."
                )

            if LC["arbustive"] > 0.0:
                lines.append(
                    f"Il manque au moins {ceil(LC["arbustive"])} m de haie arbustive ou mixte."
                )

            t1_t2 = LC["degradee"] + LC["buissonnante"]
            if t1_t2 > 0.0:
                lines.append(
                    f"Il manque au moins {ceil(t1_t2)} m de haie buissonnante, arbustive ou mixte."
                )

            t = "<br />\n".join(lines)

        return mark_safe(t % self.context)

    @property
    def hint(self):
        lines = [
            f"<strong>Linéaire attendu en compensation : {self.context["lpm"]} m.</strong><br>"
        ]

        if isclose(self.R, self.catalog["aggregated_r"]) and not isclose(
            self.context["lpm"], self.context["reduced_lpm"]
        ):
            lines.append(
                f"""
                La compensation peut être réduite à {self.context["reduced_lpm"]} m en
                proposant de planter des haies de type supérieur à celui des haies à détruire
                (<a href="https://equatorial-red-4c6.notion.site/Normandie-quels-types-de-haie-permettent-une-r-duction-de-la-compensation-attendue-2e9fe5fe47668120bdd6ec6fd14a6195" target="_blank" rel="noopener">voir le guide</a>).
                """  # noqa: E501
            )

        return mark_safe(" ".join(lines))


class SafetyCondition(PlantationCondition):
    label = "Sécurité"
    order = 10
    valid_text = "Aucune haie haute sous une ligne électrique ou téléphonique."
    invalid_text = """
        Au moins une haie haute est plantée sous une ligne électrique ou téléphonique.
        Ceci est à éviter pour des raisons de sécurité.
        Seuls des linéaires de type « haie buissonnante basse » ou « haie arbustive »
        peuvent être plantés à ces endroits.
    """

    def evaluate(self):
        unsafe_hedges = [
            h
            for h in self.hedge_data.hedges_to_plant()
            if h.hedge_type in ["alignement", "mixte"] and h.sous_ligne_electrique
        ]
        self.result = not unsafe_hedges
        return self


class StrenghteningCondition(PlantationCondition):
    RATE = 0.2
    order = 3

    label = "Renforcement de haies existantes"
    valid_text = (
        "Le renforcement ou regarnissage sur %(strengthening_length)s m convient."
    )
    invalid_text = """
        Le renforcement ou la reconnexion doit porter sur moins de 20%% de la compensation attendue.
        <br/>Il manque %(missing_plantation_length)s m de plantation nouvelle.
    """
    hint_text = """
        Jusqu’à 20%% du linéaire de compensation peuvent consister en un renforcement
        ou une reconnexion de haies existantes.
    """

    def must_display(self):
        """Should the condition be displayed?"""
        is_remplacement = self.catalog.get("reimplantation") == "remplacement"
        return not is_remplacement

    def evaluate(self):
        lpm = self.catalog["lpm"]
        length_to_plant = self.hedge_data.length_to_plant()
        length_to_plant_by_mode = defaultdict(int)
        for hedge in self.hedge_data.hedges_to_plant():
            length_to_plant_by_mode[hedge.prop("mode_plantation")] += hedge.length

        if self.R == 0.0:
            self.result = True
        elif length_to_plant < lpm:
            # la compensation n’est pas suffisante (approximatif car il y a LPm_r mais on n’en tient pas compte ici)
            self.result = (
                length_to_plant_by_mode["plantation"] > 0.8 * length_to_plant
            )  # le renforcement ne doit pas représenter plus de 20% de la plantation proposée
        else:  # // compensation suffisante (approximatif mais ok)
            self.result = (
                length_to_plant_by_mode["plantation"] > 0.8 * lpm
            )  # la plantation occupe au moins 80% de la plantation minimale

        strengthening_length = (
            length_to_plant_by_mode["renforcement"]
            + length_to_plant_by_mode["reconnexion"]
        )
        self.context = {
            "strengthening_length": ceil(strengthening_length),
            "missing_plantation_length": ceil(
                0.8 * lpm - length_to_plant_by_mode["plantation"]
            ),
        }
        return self

    @property
    def text(self):
        strengthening_length = self.context.get("strengthening_length")

        valid_text = (
            "Le renforcement ou la reconnexion sur %(strengthening_length)s m convient."
            if strengthening_length > 0
            else "Pas de renforcement ni reconnexion de haies."
        )

        t = valid_text if self.result else self.invalid_text
        return mark_safe(t % self.context)


class LineaireInterchamp(PlantationCondition):
    label = "Maintien des haies inter-champ"
    order = 5
    valid_text = "Le linéaire de haies plantées en inter-champ est suffisant."
    invalid_text = """
        Le linéaire de haies plantées en inter-champ doit être supérieur à %(length_to_remove_interchamp)s m.
        <br>Il manque au moins %(interchamp_delta)s m.
    """

    def evaluate(self):

        def interchamp_filter(h):
            return bool(h.prop("interchamp"))

        hedges_to_remove = filter(interchamp_filter, self.hedge_data.hedges_to_remove())
        length_to_remove = sum(h.length for h in hedges_to_remove)

        hedges_to_plant = filter(interchamp_filter, self.hedge_data.hedges_to_plant())
        length_to_plant = sum(h.length for h in hedges_to_plant)

        delta = length_to_remove - length_to_plant

        self.result = delta <= 0 or self.R == 0.0
        self.context = {
            "length_to_remove_interchamp": round(length_to_remove),
            "length_to_plant_interchamp": round(length_to_plant),
            "interchamp_delta": ceil(max(0, delta)),
        }
        return self


class LineaireSurTalusCondition(PlantationCondition):
    label = "Maintien des haies sur talus"
    order = 4
    valid_text = "Le linéaire de haies plantées sur talus est suffisant."
    invalid_text = """
        Le linéaire de haies plantées sur talus doit être supérieur à %(length_to_remove_talus)s m.
        <br>Il manque au moins %(talus_delta)s m.
    """

    def evaluate(self):

        def talus_filter(h):
            return h.prop("sur_talus")

        hedges_to_remove = filter(talus_filter, self.hedge_data.hedges_to_remove())
        length_to_remove = sum(h.length for h in hedges_to_remove)

        hedges_to_plant = filter(talus_filter, self.hedge_data.hedges_to_plant())
        length_to_plant = sum(h.length for h in hedges_to_plant)

        delta = length_to_remove - length_to_plant

        self.result = delta <= 0 or self.R == 0.0
        self.context = {
            "length_to_remove_talus": round(length_to_remove),
            "length_to_plant_talus": round(length_to_plant),
            "talus_delta": ceil(max(0, delta)),
        }
        return self


class EssencesBocageresCondition(PlantationCondition):
    label = "Essences bocagères"
    order = 5
    valid_text = "Toutes les haies à planter sont composées d'essences bocagères."
    invalid_text = """
        Au moins une haie à planter est composée d’essences non bocagères.
        Elles ne sont pas acceptées en guise de compensation.
    """

    def evaluate(self):

        def non_bocageres_filter(h):
            return h.prop("essences_non_bocageres")

        non_bocageres = filter(non_bocageres_filter, self.hedge_data.hedges_to_plant())
        self.result = len(list(non_bocageres)) == 0
        self.context = {}
        return self


class PlantationConditionMixin:
    """A mixin for a criterion evaluator with hedge replantation conditions.

    This is an "acceptability condition."
    """

    plantation_conditions: list[PlantationCondition]

    @abstractmethod
    def get_replantation_coefficient(self):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_replantation_coefficient` method."
        )

    def plantation_evaluate(self, hedge_data, R, catalog=None):
        results = [
            condition(hedge_data, R, self, catalog or {}).evaluate()
            for condition in self.plantation_conditions
        ]
        return results


class TreeAlignmentsCondition(PlantationCondition):
    label = "Alignements d’arbres (L350-3)"
    order = 5
    valid_text = "Le linéaire d’alignements d’arbres plantés en bord de voie ouverte au public est suffisant."
    invalid_text = """
        Le linéaire d’alignements d’arbres plantés en bord de voie ouverte au public doit être supérieur
        à %(minimum_length_to_plant_aa_bord_voie)s m.
        <br>Il manque au moins %(aa_bord_voie_delta)s m.
    """

    def must_display(self):
        """Should the condition be displayed?"""
        return self.criterion_evaluator.result_code != RESULTS.non_soumis

    def evaluate(self):
        hedges_to_remove_aa_bord_voie = self.hedge_data.hedges_filter(
            TO_REMOVE, "alignement", "bord_voie"
        )
        hedges_to_plant_aa_bord_voie = self.hedge_data.hedges_filter(
            TO_PLANT, "alignement", "bord_voie"
        )
        length_to_remove_aa_bord_voie = sum(
            h.length for h in hedges_to_remove_aa_bord_voie
        )
        length_to_plant_aa_bord_voie = sum(
            h.length for h in hedges_to_plant_aa_bord_voie
        )

        from envergo.moulinette.regulations.alignementarbres import AlignementsArbres

        r_aa = AlignementsArbres.get_result_based_replantation_coefficient(
            self.criterion_evaluator.result_code
        )

        minimum_length_to_plant_aa_bord_voie = length_to_remove_aa_bord_voie * r_aa
        aa_bord_voie_delta = (
            minimum_length_to_plant_aa_bord_voie - length_to_plant_aa_bord_voie
        )

        self.context = {
            "minimum_length_to_plant_aa_bord_voie": round(
                minimum_length_to_plant_aa_bord_voie
            ),
            "aa_bord_voie_delta": round(max(0, aa_bord_voie_delta)),
        }
        self.result = (
            length_to_plant_aa_bord_voie >= minimum_length_to_plant_aa_bord_voie
        )
        return self
