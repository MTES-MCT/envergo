from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict

from django.utils.safestring import mark_safe


class PlantationCondition(ABC):
    """Evaluator for a single plantation condition."""

    label: str
    result: bool  # if None, the condition will be filtered out
    order: int = 0
    context: dict = dict()
    valid_text: str = "Condition validée"
    invalid_text: str = "Condition non validée"
    hint_text: str = ""

    # We want to display the raw class in the debug template, so we need to
    # prevent the template engine to instanciate the class
    do_not_call_in_templates = True

    def __init__(self, hedge_data, R, catalog=None):
        self.hedge_data = hedge_data
        self.R = R
        self.catalog = catalog or {}

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
    Le linéaire total planté doit être supérieur à %(minimum_length_to_plant)s m.<br />
    Il manque au moins %(left_to_plant)s m.
    """

    def evaluate(self):
        length_to_plant = self.hedge_data.length_to_plant()
        length_to_remove = self.hedge_data.length_to_remove()
        minimum_length_to_plant = length_to_remove * self.R
        self.result = length_to_plant >= minimum_length_to_plant

        left_to_plant = max(0, minimum_length_to_plant - length_to_plant)
        self.context = {
            "R": self.R,
            "length_to_plant": round(length_to_plant),
            "length_to_remove": round(length_to_remove),
            "minimum_length_to_plant": round(minimum_length_to_plant),
            "left_to_plant": round(left_to_plant),
        }
        return self

    def must_display(self):
        return self.context["minimum_length_to_plant"] > 0


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
            "minimum_length_to_plant_pac": round(minimum_length_to_plant),
            "left_to_plant_pac": round(left_to_plant),
        }
        return self

    def must_display(self):
        return self.context["minimum_length_to_plant_pac"] > 0


class QualityCondition(PlantationCondition):
    label = "Type de haie plantée"
    order = 2
    valid_text = "La qualité écologique du linéaire planté est suffisante."
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
                    Il manque au moins {round(missing_plantation['mixte'] + missing_plantation['alignement'])} m
                    de haie mixte ou alignement d'arbres.
                    """
                )

            if missing_plantation["mixte"] > 0 or missing_plantation["degradee"] > 0:
                t.append(
                    f"""
                    Il manque au moins {round(missing_plantation['mixte'] + missing_plantation['degradee'])} m
                    de haie mixte.
                """
                )

            if missing_plantation["buissonante"] > 0:
                t.append(
                    f"""
                    Il manque au moins {round(missing_plantation['buissonante'] + missing_plantation['arbustive'])} m
                    de haie basse ou arbustive.
                """
                )

            if missing_plantation["arbustive"] > 0:
                t.append(
                    f"""
                    Il manque au moins {round(missing_plantation['arbustive'])} m de haie arbustive.
                """
                )

        return mark_safe("<br />\n".join(t))


HEDGE_TYPES = OrderedDict(
    [
        ("mixte", "mixte"),
        ("alignement", "alignement"),
        ("arbustive", "arbustive"),
        ("buissonnante", "buissonnante"),
        ("degradee", "dégradée"),
    ]
)


class CalvadosQualityCondition(PlantationCondition):
    label = "Type de haie plantée"
    order = 2
    valid_text = "La qualité écologique du linéaire planté est suffisante."
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
    hint_text = """
        Linéaire attendu en compensation : %(lpm)s m.
        La compensation peut être réduite à %(reduced_lpm)s m en proposant de planter
        des haies mixtes plutôt que de type identiqe aux haies à détruire.
    """

    def evaluate(self):
        is_remplacement = self.catalog.get("reimplantation") == "remplacement"
        LD = defaultdict(int)  # linéaire à détruire
        LC = defaultdict(int)  # linéaire à compenser
        LP = defaultdict(int)  # linéaire à planter

        # Les haies à planter
        for hedge in self.hedge_data.hedges_to_plant():
            LP[hedge.hedge_type] += hedge.length

        # On calcule les longueurs à compenser, le r dépend de chaque haie
        for hedge in self.hedge_data.hedges_to_remove():
            if hedge.length <= 10:
                r = 0
            elif hedge.length <= 20:
                r = 1
            elif is_remplacement and hedge.mode_destruction == "coupe_a_blanc":
                r = 1
            else:
                r = 2

            LD[hedge.hedge_type] += hedge.length
            LC[hedge.hedge_type] += hedge.length * r

        # Le taux de compensation ne peut pas descendre sous 1:1
        hedge_keys = HEDGE_TYPES.keys()
        for hedge_type in hedge_keys:
            LC[hedge_type] = max(LC[hedge_type], LD[hedge_type])

        # On calcule le linéaire total à compenser pour l'affichage
        lpm = sum(LC.values())
        reduced_lpm = 0
        for t, l in LC.items():
            reduced_lpm += l * 0.8 if t != "mixte" else l
        self.context = {
            "lpm": round(lpm),
            "reduced_lpm": round(reduced_lpm),
        }

        # On calcule l'application des compensations
        # Pour chaque linéaire à compenser, on réparti les linéaires à planter
        # en fonction des substitutions possibles.
        for hedge_type in hedge_keys:
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
        self.context.update({"LC": LC})

        return self

    @property
    def text(self):
        if self.result:
            t = self.valid_text
        else:
            lines = [self.invalid_text]
            for hedge_type, length in self.context["LC"].items():
                if length > 0.0:
                    lines.append(
                        f"""
                        Il reste à compenser au moins {round(length)} m de haie
                        {HEDGE_TYPES[hedge_type]}.
                        """
                    )
            t = "<br />\n".join(lines)

        return mark_safe(t % self.context)


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

    label = "Renforcement"
    valid_text = (
        "Le renforcement ou regarnissage sur %(strengthening_length)s m convient."
    )
    invalid_text = """
        Le renforcement ou regarnissage doit porter sur moins de %(strengthening_max)s m.
        <br>Il y a %(strengthening_excess)s m en excès.
    """
    hint_text = """
        La compensation peut consister en un renforcement ou regarnissage de haies
        existantes, dans la limite de 20%% du linéaire total à planter.
    """

    def evaluate(self):
        is_remplacement = self.catalog.get("reimplantation") == "remplacement"
        if is_remplacement:
            self.result = None
            return self

        length_to_plant = self.hedge_data.length_to_plant()
        strengthening_length = 0.0
        for hedge in self.hedge_data.hedges_to_plant():
            if hedge.prop("mode_plantation") in ("renforcement", "reconnexion"):
                strengthening_length += hedge.length

        length_to_plant = self.hedge_data.length_to_plant()
        length_to_remove = self.hedge_data.length_to_remove()
        minimum_length_to_plant = length_to_remove * self.R

        strengthening_max = minimum_length_to_plant * self.RATE
        self.result = strengthening_length <= strengthening_max
        self.context = {
            "length_to_plant": round(length_to_plant),
            "length_to_remove": round(length_to_remove),
            "minimum_length_to_plant": round(minimum_length_to_plant),
            "strengthening_max": round(strengthening_max),
            "strengthening_length": round(strengthening_length),
            "strengthening_excess": round(strengthening_length)
            - round(strengthening_max),
        }
        return self

    @property
    def text(self):
        length = self.context.get("strengthening_length")
        valid_text = (
            "Le renforcement ou regarnissage sur %(strengthening_length)s m convient."
            if length > 0
            else "Pas de renforcement ou regarnissage."
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
            return h.prop("position") == "interchamp"

        hedges_to_remove = filter(interchamp_filter, self.hedge_data.hedges_to_remove())
        length_to_remove = sum(h.length for h in hedges_to_remove)

        hedges_to_plant = filter(interchamp_filter, self.hedge_data.hedges_to_plant())
        length_to_plant = sum(h.length for h in hedges_to_plant)

        delta = length_to_remove - length_to_plant

        self.result = delta <= 0
        self.context = {
            "length_to_remove_interchamp": round(length_to_remove),
            "length_to_plant interchamp": round(length_to_plant),
            "interchamp_delta": round(max(0, delta)),
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

        self.result = delta <= 0
        self.context = {
            "length_to_remove_talus": round(length_to_remove),
            "length_to_plant talus": round(length_to_plant),
            "talus_delta": round(max(0, delta)),
        }
        return self


class PlantationConditionMixin:
    """A mixin for a criterion evaluator with hedge replantation conditions.

    This is an "acceptability condition."
    """

    plantation_conditions: list[PlantationCondition]

    def get_replantation_coefficient(self):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.get_replantation_coefficient` method."
        )

    def plantation_evaluate(self, hedge_data, R, catalog=None):
        results = [
            condition(hedge_data, R, catalog or {}).evaluate()
            for condition in self.plantation_conditions
        ]
        return results
