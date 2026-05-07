from abc import ABC, abstractmethod
from collections import defaultdict
from math import ceil, isclose

from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import TO_PLANT, TO_REMOVE, HedgeTypeBase, HedgeTypeFactory


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
        """Whether this condition should appear in the simulation results.

        Subclasses override to hide conditions that are irrelevant for a given
        project (e.g. no compensation required, so nothing to check).
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


class BaseQualityCondition(PlantationCondition):
    """Base class for hedge quality compensation conditions.

    Verifies that planted hedges match the ecological quality of removed hedges.
    Each type of removed hedge must be compensated by planting the same type or
    an acceptable higher-quality substitute, according to a regulation-specific
    compensation table.
    """

    label = "Type de haie plantée"
    order = 2
    valid_text = "Le type de haie plantée convient."
    invalid_text = """
      Le type de haie plantée n'est pas adapté au vu de celui des haies détruites.
    """

    # {removed_type: [acceptable_planted_types, preferred first]}
    # Dict iteration order defines processing priority.
    compensations: dict[str, list[str]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.HedgeType = HedgeTypeFactory.build_from_context(
            self.criterion_evaluator.moulinette.config.single_procedure
        )

    @abstractmethod
    def get_amounts_to_compensate(self) -> dict[str, float]:
        """Return the total hedge length requiring compensation, keyed by hedge type.

        Each key is a HedgeTypeBase value (e.g. ``HedgeTypeBase.MIXTE``), each
        value is the total length in metres that must be compensated for that
        type. Types with zero compensation may be omitted or set to 0.
        """
        raise NotImplementedError

    def get_amounts_planted(self) -> dict[str, float]:
        """Return per-type lengths planted, excluding degradee."""
        lengths = defaultdict(float)
        for hedge in self.hedge_data.hedges_to_plant():
            lengths[hedge.hedge_type] += hedge.length
        return {
            key: lengths[key]
            for key, _ in self.HedgeType.choices
            if key != HedgeTypeBase.DEGRADEE
        }

    def get_compensation_rate(self, removed_type, planted_type):
        """Rate applied when compensating removed_type with planted_type.

        Returns 1.0 by default (1:1 compensation). Override in subclasses
        to grant bonuses for planting higher-quality types.
        """
        return 1.0

    def apply_result_overrides(self):
        """Hook for regulation-specific result overrides (e.g. L350)."""
        pass

    def build_context(self, initial_deficits, initial_compensating):
        """Populate self.context with data for text/hint rendering.

        Called after the compensation algorithm runs. ``self.remaining``
        holds the per-type deficits that were not filled.
        """
        self.context = {}

    def evaluate(self):
        """Evaluate whether planted hedges compensate the quality of removed hedges.

        Two-phase algorithm:

         1) each type absorbs its own planted amount
         2) remaining deficits are filled by higher-quality substitutes
        according to ``self.compensations``.
        """
        initial_deficits = self.get_amounts_to_compensate()
        initial_compensating = self.get_amounts_planted()

        deficits, compensating = self.match_same_types(
            initial_deficits, initial_compensating
        )
        deficits, compensating = self.fill_with_substitutes(deficits, compensating)

        # If all deficits were compensated, condition is validated
        self.result = all(v <= 0 for v in deficits.values())

        self.remaining = deficits
        self.apply_result_overrides()
        self.build_context(initial_deficits, initial_compensating)
        return self

    def compensate(self, deficits, compensating, deficit_type, substitute):
        """Use a substitute's planted amount to fill a deficit.

        Mutates both dicts in place. Does nothing if either side is empty.
        """
        if deficits.get(deficit_type, 0) <= 0 or compensating.get(substitute, 0) <= 0:
            return
        rate = self.get_compensation_rate(deficit_type, substitute)
        filled = min(deficits[deficit_type], compensating[substitute] / rate)
        deficits[deficit_type] -= filled
        compensating[substitute] -= filled * rate

    def match_same_types(self, initial_deficits, initial_compensating):
        """Return (deficits, compensating) after absorbing same-type matches."""
        deficits = dict(initial_deficits)
        compensating = dict(initial_compensating)
        for hedge_type in deficits:
            self.compensate(deficits, compensating, hedge_type, hedge_type)
        return deficits, compensating

    def fill_with_substitutes(self, initial_deficits, initial_compensating):
        """Return (deficits, compensating) after cross-type substitution."""
        deficits = dict(initial_deficits)
        compensating = dict(initial_compensating)
        for deficit_type, substitutes in self.compensations.items():
            for substitute in substitutes:
                if substitute == deficit_type:
                    continue
                self.compensate(deficits, compensating, deficit_type, substitute)
        return deficits, compensating

    def must_display(self):
        """True when any hedge type requires compensation."""
        amounts = self.get_amounts_to_compensate()
        return sum(amounts.values()) > 0


class AisneQualityCondition(BaseQualityCondition):
    """Quality condition for Aisne (EP Aisne).

    Uses a flat replantation coefficient R for all hedges.
    Substitution is 1:1 with no quality-upgrade bonus.
    """

    compensations = {
        HedgeTypeBase.ALIGNEMENT: [HedgeTypeBase.ALIGNEMENT, HedgeTypeBase.MIXTE],
        HedgeTypeBase.BUISSONNANTE: [
            HedgeTypeBase.BUISSONNANTE,
            HedgeTypeBase.ARBUSTIVE,
        ],
        HedgeTypeBase.DEGRADEE: [
            HedgeTypeBase.BUISSONNANTE,
            HedgeTypeBase.ARBUSTIVE,
            HedgeTypeBase.MIXTE,
        ],
        HedgeTypeBase.ARBUSTIVE: [HedgeTypeBase.ARBUSTIVE],
        HedgeTypeBase.MIXTE: [HedgeTypeBase.MIXTE],
    }

    def get_amounts_to_compensate(self):
        """Flat coefficient: length_removed × R for each type."""
        lengths_by_type = defaultdict(int)
        for hedge in self.hedge_data.hedges_to_remove():
            lengths_by_type[hedge.hedge_type] += hedge.length
        return {key: self.R * lengths_by_type[key] for key, _ in self.HedgeType.choices}

    def build_context(self, initial_deficits, initial_compensating):
        self.context = {"missing_plantation": self.remaining}

    @property
    def text(self):
        """Return the text to display for the condition."""
        if self.result:
            return mark_safe(self.valid_text)

        mp = self.context["missing_plantation"]
        lines = [
            "Le type de haie plantée ne permet pas de compenser "
            "la qualité écologique des haies détruites."
        ]

        if mp.get(HedgeTypeBase.ALIGNEMENT, 0) > 0:
            total = mp.get(HedgeTypeBase.MIXTE, 0) + mp.get(HedgeTypeBase.ALIGNEMENT, 0)
            lines.append(
                format_html(
                    "Il manque au moins {} m de {} ou alignement d'arbres.",
                    ceil(total),
                    self.HedgeType.MIXTE.label.lower(),
                )
            )

        if mp.get(HedgeTypeBase.MIXTE, 0) > 0 or mp.get(HedgeTypeBase.DEGRADEE, 0) > 0:
            total = mp.get(HedgeTypeBase.MIXTE, 0) + mp.get(HedgeTypeBase.DEGRADEE, 0)
            lines.append(
                format_html("Il manque au moins {} m de haie mixte.", ceil(total))
            )

        if mp.get(HedgeTypeBase.BUISSONNANTE, 0) > 0:
            total = mp.get(HedgeTypeBase.BUISSONNANTE, 0) + mp.get(
                HedgeTypeBase.ARBUSTIVE, 0
            )
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie basse ou arbustive.",
                    ceil(total),
                )
            )

        if mp.get(HedgeTypeBase.ARBUSTIVE, 0) > 0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie arbustive.",
                    ceil(mp.get(HedgeTypeBase.ARBUSTIVE, 0)),
                )
            )

        return format_html_join(mark_safe("<br />\n"), "{}", ((l,) for l in lines))


class NormandieQualityCondition(BaseQualityCondition):
    """Quality condition for Normandie (EP Normandie).

    Uses pre-computed per-hedge coefficients from a density/zone matrix.
    Cross-type compensation grants a 20% length reduction (rate 0.8),
    except buissonnante compensating degradee (rate 1.0).
    """

    compensations = {
        HedgeTypeBase.ALIGNEMENT: [HedgeTypeBase.ALIGNEMENT, HedgeTypeBase.MIXTE],
        HedgeTypeBase.MIXTE: [HedgeTypeBase.MIXTE],
        HedgeTypeBase.ARBUSTIVE: [HedgeTypeBase.ARBUSTIVE, HedgeTypeBase.MIXTE],
        HedgeTypeBase.BUISSONNANTE: [
            HedgeTypeBase.BUISSONNANTE,
            HedgeTypeBase.ARBUSTIVE,
            HedgeTypeBase.MIXTE,
        ],
        HedgeTypeBase.DEGRADEE: [
            HedgeTypeBase.BUISSONNANTE,
            HedgeTypeBase.ARBUSTIVE,
            HedgeTypeBase.MIXTE,
        ],
    }

    def get_amounts_to_compensate(self):
        """Read pre-computed LC from the catalog."""
        return self.catalog["LC"].copy()

    def get_compensation_rate(self, removed_type, planted_type):
        """0.8 rate for quality upgrades, except buissonnante→degradee."""
        is_same_type = planted_type == removed_type
        is_buissonnante_for_degradee = (
            removed_type == HedgeTypeBase.DEGRADEE
            and planted_type == HedgeTypeBase.BUISSONNANTE
        )
        return 1.0 if (is_same_type or is_buissonnante_for_degradee) else 0.8

    def apply_result_overrides(self):
        """Force pass for L350 result codes."""
        result_code = self.criterion_evaluator.result_code
        if result_code in ("dispense_L350", "a_verifier_L350"):
            self.result = True

    def build_context(self, initial_deficits, initial_compensating):
        self.context = {
            "lpm": ceil(self.catalog["lpm"]),
            "reduced_lpm": ceil(self.catalog["reduced_lpm"]),
            "LC": self.remaining,
            "LP": initial_compensating,
            "LPm": initial_deficits,
            "lm": sum(self.remaining.values()),
            "lp": sum(initial_compensating.values()),
        }

    @property
    def text(self):
        if self.result:
            return mark_safe(self.valid_text)

        LC = self.context["LC"]
        lines = [self.invalid_text]

        if LC[HedgeTypeBase.MIXTE] > 0.0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie mixte.",
                    ceil(LC[HedgeTypeBase.MIXTE]),
                )
            )

        if LC[HedgeTypeBase.ALIGNEMENT] > 0.0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie mixte ou d'alignement d'arbres.",
                    ceil(LC[HedgeTypeBase.ALIGNEMENT]),
                )
            )

        if LC[HedgeTypeBase.ARBUSTIVE] > 0.0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie arbustive ou mixte.",
                    ceil(LC[HedgeTypeBase.ARBUSTIVE]),
                )
            )

        t1_t2 = LC[HedgeTypeBase.DEGRADEE] + LC[HedgeTypeBase.BUISSONNANTE]
        if t1_t2 > 0.0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie buissonnante, arbustive ou mixte.",
                    ceil(t1_t2),
                )
            )

        return format_html_join(mark_safe("<br />\n"), "{}", ((l,) for l in lines))

    @property
    def hint(self):
        lines = [
            f"<strong>Linéaire attendu en compensation : {self.context['lpm']} m.</strong><br>"
        ]

        if isclose(self.R, self.catalog["aggregated_r"]) and not isclose(
            self.context["lpm"], self.context["reduced_lpm"]
        ):
            lines.append(
                f"""
                La compensation peut être réduite à {self.context["reduced_lpm"]} m en
                proposant de planter des haies de type supérieur à celui des haies à détruire
                (<a href="{settings.HAIE_FAQ_URLS["NORMANDIE_HEDGES_FOR_COMPENSATION_REDUCTION"]}" target="_blank" rel="noopener">voir le guide</a>).
                """  # noqa: E501
            )

        return mark_safe(" ".join(lines))


class RUQualityCondition(BaseQualityCondition):
    """Quality condition for the régime unique (EP RU).

    Uses per-hedge coefficients from zone config plus an EP bonus (majoration)
    to compute the amounts to compensate. Alignement and degradee hedges are
    excluded. No quality-upgrade rate bonus — substitution is always 1:1.
    """

    compensations = {
        HedgeTypeBase.BUISSONNANTE: [
            HedgeTypeBase.BUISSONNANTE,
            HedgeTypeBase.ARBUSTIVE,
            HedgeTypeBase.MIXTE,
        ],
        HedgeTypeBase.ARBUSTIVE: [HedgeTypeBase.ARBUSTIVE, HedgeTypeBase.MIXTE],
        HedgeTypeBase.MIXTE: [HedgeTypeBase.MIXTE],
    }

    def get_amounts_to_compensate(self):
        """Per-hedge coefficient from zone config, plus EP bonus."""
        coefficients = self.catalog["ru_per_hedge_coefficients"]
        bonus = self.criterion_evaluator.get_ep_ru_bonus()
        lc = defaultdict(float)
        for hedge in self.hedge_data.hedges_to_remove():
            if hedge.id in coefficients:
                r = coefficients[hedge.id] + bonus
                lc[hedge.hedge_type] += hedge.length * r
        return dict(lc)

    @property
    def text(self):
        if self.result:
            return mark_safe(self.valid_text)

        lines = [self.invalid_text]

        if self.remaining.get(HedgeTypeBase.MIXTE, 0) > 0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie arborée.",
                    ceil(self.remaining[HedgeTypeBase.MIXTE]),
                )
            )

        if self.remaining.get(HedgeTypeBase.ARBUSTIVE, 0) > 0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie arbustive ou arborée.",
                    ceil(self.remaining[HedgeTypeBase.ARBUSTIVE]),
                )
            )

        if self.remaining.get(HedgeTypeBase.BUISSONNANTE, 0) > 0:
            lines.append(
                format_html(
                    "Il manque au moins {} m de haie buissonnante, arbustive ou arborée.",
                    ceil(self.remaining[HedgeTypeBase.BUISSONNANTE]),
                )
            )

        return format_html_join(mark_safe("<br />\n"), "{}", ((l,) for l in lines))


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
