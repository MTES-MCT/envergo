from abc import ABC, abstractmethod
from collections import defaultdict
from math import ceil, isclose

from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeTypeBase, HedgeTypeFactory


def compute_lengths_per_type(hedges, coefficients):
    """Compute per-type destruction and compensation lengths from per-hedge coefficients.

    Returns (destruction, compensation) where destruction is {type: raw length}
    and compensation is {type: length × R} for hedges that have a coefficient.
    """
    destruction = defaultdict(float)
    compensation = defaultdict(float)
    for hedge in hedges:
        if hedge.id in coefficients:
            destruction[hedge.hedge_type] += hedge.length
            compensation[hedge.hedge_type] += hedge.length * coefficients[hedge.id]
    return dict(destruction), dict(compensation)


def apply_cross_type_reduction(compensation, destruction, hedge_types):
    """Apply the Normandie 20% cross-type reduction, floored at 1:1 ratio.

    When planting a higher-quality type than what was removed, the required
    compensation length is reduced by 20%. The reduction cannot go below the
    raw destruction length (1:1 floor). MIXTE (top quality) gets no reduction.

    Returns a dict mapping each hedge type to its reduced compensation length.
    """
    reduced = {}
    for hedge_type in hedge_types:
        amount = compensation.get(hedge_type, 0.0)
        if hedge_type != HedgeTypeBase.MIXTE:
            amount *= 0.8
        reduced[hedge_type] = max(amount, destruction.get(hedge_type, 0.0))
    return reduced


class PlantationCondition(ABC):
    """Evaluator for a single plantation condition."""

    label: str
    result: bool
    order: int = 0
    valid_text: str = "Condition validée"
    invalid_text: str = "Condition non validée"
    hint_text: str = ""

    # We want to display the raw class in the debug template, so we need to
    # prevent the template engine to instanciate the class
    do_not_call_in_templates = True

    def __init__(self, hedges, R, criterion_evaluator, catalog=None):
        """Initialize a plantation condition.

        Conditions should be instantiated via
        ``PlantationConditionMixin.plantation_evaluate()``, which populates the
        catalog with the correct ``effective_coefficients`` entry.
        """
        self.hedges = hedges
        self.R = R
        self.catalog = dict(catalog) if catalog else {}
        self.criterion_evaluator = criterion_evaluator
        self.context = {}

    def must_display(self):
        """Whether this condition should appear in the simulation results.

        Subclasses override to hide conditions that are irrelevant for a given
        project (e.g. no compensation required, so nothing to check).
        """
        return True

    def is_stricter_than(self, other):
        """Whether self imposes stricter requirements than other.

        Only meaningful for conditions of the same class — raises TypeError
        otherwise. Delegates to compare_strictness for the actual comparison.
        Subclasses should override compare_strictness, not this method.
        """
        if type(self) is not type(other):
            raise TypeError(
                f"Cannot compare strictness between {type(self).__name__} "
                f"and {type(other).__name__}"
            )
        return self.compare_strictness(other)

    def compare_strictness(self, other):
        """Compare strictness with another instance of the same condition class.

        Called by is_stricter_than after type validation. Override in subclasses
        that can be duplicated across evaluators. Returns False by default,
        meaning neither instance claims to be stricter — deduplication keeps
        the first one in evaluator iteration order (deterministic).
        """
        return False

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
        length_to_plant = self.hedges.to_plant().length
        length_to_remove = self.hedges.to_remove().length

        minimum_length_to_plant = length_to_remove * self.R
        self.result = length_to_plant >= minimum_length_to_plant

        left_to_plant = max(0, minimum_length_to_plant - length_to_plant)
        self.context = {
            "R": self.R,
            "length_to_plant": round(length_to_plant),
            "length_to_remove": round(length_to_remove),
            "minimum_length_to_plant": ceil(minimum_length_to_plant),
            "left_to_plant": ceil(left_to_plant),
            "length_to_check": ceil(minimum_length_to_plant),
        }
        return self

    def must_display(self):
        return self.context["length_to_check"] > 0


class RUMinLengthCondition(MinLengthCondition):
    """Evaluate if there is enough hedges to plant in the project.

    The difference with the base MinLengthCondition:
     - MinLengthCondition uses the global R, which is the max R for each evaluators.
     - RuMinLengthCondition uses the specific R for the current evaluator.
    """

    def evaluate(self):
        # Override R with the local evaluator value
        self.R = self.criterion_evaluator.get_replantation_coefficient()
        return super().evaluate()

    def compare_strictness(self, other):
        """The condition requiring the longer minimum length is stricter."""
        return self.context["length_to_check"] > other.context["length_to_check"]


class NormandieMinLengthCondition(MinLengthCondition):
    """MinLengthCondition with cross-type reduction for Normandie.

    When planting a higher-quality type than the removed hedge, the required
    compensation length can be reduced by 20% (floored at 1:1). This condition
    uses the reduced minimum when applicable.
    """

    def compute_reduced_minimum(self):
        """Compute the total reduced minimum length from effective coefficients.

        Fetches per-hedge coefficients from the catalog, computes per-type
        destruction and compensation lengths, applies the cross-type reduction,
        and returns the sum across all types.
        """
        coefficients = self.criterion_evaluator.effective_coefficients
        destruction, compensation = compute_lengths_per_type(
            self.hedges.to_remove(), coefficients
        )
        hedge_type_enum = HedgeTypeFactory.build_from_context(
            self.criterion_evaluator.moulinette.config.single_procedure
        )
        reduced = apply_cross_type_reduction(
            compensation, destruction, hedge_type_enum.values
        )
        return sum(reduced.values())

    def evaluate(self):
        """Evaluate minimum length with optional cross-type reduction.

        Runs the base MinLengthCondition logic, then applies the Normandie
        reduction when R matches the aggregated coefficient. The reduced
        minimum replaces the base minimum only if it is strictly lower.
        """
        super().evaluate()

        reduced_lpm = self.compute_reduced_minimum()
        if isclose(self.R, self.catalog["aggregated_r"]):
            length_to_plant = self.context["length_to_plant"]
            length_to_check = reduced_lpm
            self.result = length_to_plant >= length_to_check

            left_to_plant = max(0, length_to_check - length_to_plant)
            self.context["left_to_plant"] = ceil(left_to_plant)
            self.context["length_to_check"] = ceil(length_to_check)

            if round(length_to_check) < round(self.context["minimum_length_to_plant"]):
                self.context["reduced_minimum_length_to_plant"] = ceil(length_to_check)

        return self


class PacParcelCondition(PlantationCondition):
    """Checks that enough hedges are planted on PAC parcels."""

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

        length_to_plant = self.hedges.to_plant().pac().length
        minimum_length_to_plant = self.hedges.to_remove().pac().length * R
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

    # {removed_type: [acceptable_planted_types, preferred first]}.
    # Iteration order matters: types listed first are filled first by the
    # substitution algorithm, so place the hardest-to-fill types first.
    compensations: dict[str, list[str]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hedge_type_enum = HedgeTypeFactory.build_from_context(
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
        for hedge in self.hedges.to_plant():
            lengths[hedge.hedge_type] += hedge.length
        return {
            key: lengths[key]
            for key, _ in self.hedge_type_enum.choices
            if key != HedgeTypeBase.DEGRADEE
        }

    def get_compensation_rate(self, removed_type, planted_type):
        """Rate applied when compensating removed_type with planted_type.

        Returns 1.0 by default (1:1 compensation). Override in subclasses
        to grant bonuses for planting higher-quality types.
        """
        return 1.0

    def apply_result_overrides(self):
        """Hook for regulation-specific result overrides after compensation."""
        pass

    def pad_all_types(self, sparse_dict):
        """Return a copy with all hedge types present, defaulting missing ones to 0.0.

        The Django template ``get_item`` filter raises KeyError on missing keys,
        so the template expects every hedge type to be present in the dict.
        """
        padded = {t: 0.0 for t in self.hedge_type_enum.values}
        padded.update(sparse_dict)
        return padded

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

        self.result = all(v <= 0 for v in deficits.values())

        self.remaining = deficits
        self.apply_result_overrides()
        self.build_context(initial_deficits, initial_compensating)
        return self

    def compensate(self, deficits, compensating, deficit_type, substitute_type):
        """Use a substitute's planted amount to fill a deficit.

        Mutates both dicts in place. Does nothing if either side is empty.
        """
        if (
            deficits.get(deficit_type, 0) <= 0
            or compensating.get(substitute_type, 0) <= 0
        ):
            return
        rate = self.get_compensation_rate(deficit_type, substitute_type)
        filled = min(deficits[deficit_type], compensating[substitute_type] / rate)
        deficits[deficit_type] -= filled
        compensating[substitute_type] -= filled * rate

    def match_same_types(self, initial_deficits, initial_compensating):
        """Return (deficits, compensating) after absorbing same-type matches."""
        deficits = dict(initial_deficits)
        compensating = dict(initial_compensating)
        for hedge_type in list(deficits):
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

    def deficit_line(self, amount, type_description):
        """Format a single deficit message, or None if no deficit."""
        if amount <= 0:
            return None
        return format_html(
            "Il manque au moins {} m de {}.",
            ceil(amount),
            type_description,
        )

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
        for hedge in self.hedges.to_remove():
            lengths_by_type[hedge.hedge_type] += hedge.length
        return {
            key: self.R * lengths_by_type[key]
            for key, _ in self.hedge_type_enum.choices
        }

    def build_context(self, initial_deficits, initial_compensating):
        self.context = {"missing_plantation": self.remaining}

    @property
    def text(self):
        """Return the text to display for the condition."""
        if self.result:
            return mark_safe(self.valid_text)

        mp = self.context["missing_plantation"]
        mixte = mp.get(HedgeTypeBase.MIXTE, 0)
        alignement = mp.get(HedgeTypeBase.ALIGNEMENT, 0)
        arbustive = mp.get(HedgeTypeBase.ARBUSTIVE, 0)
        buissonnante = mp.get(HedgeTypeBase.BUISSONNANTE, 0)
        degradee = mp.get(HedgeTypeBase.DEGRADEE, 0)

        mixte_label = self.hedge_type_enum.MIXTE.label.lower()
        lines = [self.invalid_text]
        if alignement > 0:
            lines.append(
                self.deficit_line(
                    mixte + alignement, f"{mixte_label} ou alignement d’arbres"
                )
            )
        lines.append(self.deficit_line(mixte + degradee, "haie mixte"))
        if buissonnante > 0:
            lines.append(
                self.deficit_line(buissonnante + arbustive, "haie basse ou arbustive")
            )
        lines.append(self.deficit_line(arbustive, "haie arbustive"))

        lines = [line for line in lines if line is not None]
        return format_html_join(
            mark_safe("<br />\n"), "{}", ((line,) for line in lines)
        )


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
        """Compute LC from effective per-hedge coefficients."""
        coefficients = self.criterion_evaluator.effective_coefficients
        _, compensation = compute_lengths_per_type(
            self.hedges.to_remove(), coefficients
        )
        return compensation

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
        """Populate context with compensation data for the instructor template.

        Keys use the short abbreviations from the regulation spec:
        LC — remaining deficits after compensation (Longueur à Compenser restante),
        LP — planted lengths per type, LPm — minimum required per type,
        LPm_r — reduced minimum per type (after cross-type reduction),
        lpm/reduced_lpm — scalar totals, lm/lp — scalar remaining/planted.
        """
        coefficients = self.criterion_evaluator.effective_coefficients
        destruction, _ = compute_lengths_per_type(self.hedges.to_remove(), coefficients)
        lpm_r = apply_cross_type_reduction(
            initial_deficits, destruction, self.hedge_type_enum.values
        )

        self.context = {
            "lpm": ceil(sum(initial_deficits.values())),
            "reduced_lpm": ceil(sum(lpm_r.values())),
            "LPm_r": lpm_r,
            "LC": self.pad_all_types(self.remaining),
            "LP": self.pad_all_types(initial_compensating),
            "LPm": self.pad_all_types(initial_deficits),
            "lm": sum(self.remaining.values()),
            "lp": sum(initial_compensating.values()),
        }

    @property
    def text(self):
        if self.result:
            return mark_safe(self.valid_text)

        LC = self.context["LC"]
        lines = [
            self.invalid_text,
            self.deficit_line(LC.get(HedgeTypeBase.MIXTE, 0), "haie mixte"),
            self.deficit_line(
                LC.get(HedgeTypeBase.ALIGNEMENT, 0),
                "haie mixte ou d’alignement d’arbres",
            ),
            self.deficit_line(
                LC.get(HedgeTypeBase.ARBUSTIVE, 0), "haie arbustive ou mixte"
            ),
            self.deficit_line(
                LC.get(HedgeTypeBase.DEGRADEE, 0)
                + LC.get(HedgeTypeBase.BUISSONNANTE, 0),
                "haie buissonnante, arbustive ou mixte",
            ),
        ]
        lines = [line for line in lines if line is not None]
        return format_html_join(
            mark_safe("<br />\n"), "{}", ((line,) for line in lines)
        )

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
                (<a href="{settings.HAIE_FAQ_URLS["NORMANDIE_HEDGES_FOR_COMPENSATION_REDUCTION"]}"
                target="_blank" rel="noopener">voir le guide</a>).
                """
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
        """Per-hedge compensation amounts from effective coefficients."""
        coefficients = self.criterion_evaluator.effective_coefficients
        lc = defaultdict(float)
        for hedge in self.hedges.to_remove():
            if hedge.id in coefficients:
                lc[hedge.hedge_type] += hedge.length * coefficients[hedge.id]
        return dict(lc)

    def build_context(self, initial_deficits, initial_compensating):
        """Populate context with compensation data for the instructor template.

        RU has no cross-type rate reduction, so LPm_r equals LPm.
        """
        self.context = {
            "lpm": ceil(sum(initial_deficits.values())),
            "reduced_lpm": ceil(sum(initial_deficits.values())),
            "LPm_r": self.pad_all_types(initial_deficits),
            "LC": self.pad_all_types(self.remaining),
            "LP": self.pad_all_types(initial_compensating),
            "LPm": self.pad_all_types(initial_deficits),
            "lm": sum(self.remaining.values()),
            "lp": sum(initial_compensating.values()),
        }

    def compare_strictness(self, other):
        return self.context["lpm"] > other.context["lpm"]

    @property
    def text(self):
        if self.result:
            return mark_safe(self.valid_text)

        r = self.remaining
        lines = [
            self.invalid_text,
            self.deficit_line(r.get(HedgeTypeBase.MIXTE, 0), "haie arborée"),
            self.deficit_line(
                r.get(HedgeTypeBase.ARBUSTIVE, 0), "haie arbustive ou arborée"
            ),
            self.deficit_line(
                r.get(HedgeTypeBase.BUISSONNANTE, 0),
                "haie buissonnante, arbustive ou arborée",
            ),
        ]
        lines = [line for line in lines if line is not None]
        return format_html_join(
            mark_safe("<br />\n"), "{}", ((line,) for line in lines)
        )


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
            for h in self.hedges.to_plant()
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

    def compute_lpm(self):
        """Compute the total compensation length from effective per-hedge coefficients."""
        coefficients = self.criterion_evaluator.effective_coefficients
        _, compensation = compute_lengths_per_type(
            self.hedges.to_remove(), coefficients
        )
        return sum(compensation.values())

    def evaluate(self):
        lpm = self.compute_lpm()
        hedges_to_plant = self.hedges.to_plant()
        length_to_plant = hedges_to_plant.length
        length_to_plant_by_mode = defaultdict(int)
        for hedge in hedges_to_plant:
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

        hedges_to_remove = filter(interchamp_filter, self.hedges.to_remove())
        length_to_remove = sum(h.length for h in hedges_to_remove)

        hedges_to_plant = filter(interchamp_filter, self.hedges.to_plant())
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

        hedges_to_remove = filter(talus_filter, self.hedges.to_remove())
        length_to_remove = sum(h.length for h in hedges_to_remove)

        hedges_to_plant = filter(talus_filter, self.hedges.to_plant())
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

        non_bocageres = filter(non_bocageres_filter, self.hedges.to_plant())
        self.result = len(list(non_bocageres)) == 0
        self.context = {}
        return self


class PlantationConditionMixin:
    """A mixin for a criterion evaluator with hedge replantation conditions.

    This is an "acceptability condition."
    """

    plantation_conditions: list[PlantationCondition]

    # Evaluator result_codes for which plantation conditions are irrelevant.
    # Uses result_code (string), not result (RESULTS enum), because different
    # result_codes can map to the same enum value — e.g. Normandie's
    # "dispense_10m" maps to RESULTS.dispense but should still produce conditions.
    plantation_skip_results: frozenset = frozenset()

    @abstractmethod
    def get_replantation_coefficient(self):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_replantation_coefficient` method."
        )

    @property
    def effective_coefficients(self):
        """Per-hedge compensation coefficients used by plantation conditions.

        Returns a ``{hedge_id: float}`` dict mapping each hedge-to-remove to
        its compensation multiplier. Override in evaluators whose conditions
        depend on per-hedge coefficients.
        """
        return {}

    def plantation_evaluate(self, R, catalog=None):
        """Evaluate all plantation conditions for this evaluator.

        Returns an empty list when the evaluator's result_code is in
        plantation_skip_results — those states mean no plantation obligation
        exists for this evaluator, so conditions should not be created at all.
        """
        if self.result_code in self.plantation_skip_results:
            return []

        catalog = dict(catalog or {})
        return [
            condition(self.hedges, R, self, catalog).evaluate()
            for condition in self.plantation_conditions
        ]


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
        length_to_remove_aa_bord_voie = self.hedges.to_remove().l350_3().length
        length_to_plant_aa_bord_voie = self.hedges.to_plant().l350_3().length

        from envergo.moulinette.regulations.alignementarbres import (
            AlignementsArbresL3503,
        )

        r_aa = AlignementsArbresL3503.get_result_based_replantation_coefficient(
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
