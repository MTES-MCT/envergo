from collections import defaultdict


class PlantationCondition:
    """Evaluator for a single plantation condition."""

    result: bool
    context: dict = dict()
    valid_text: str = "Condition validée"
    invalid_text: str = "Condition non validée"

    def __init__(self, hedge_data, R):
        self.hedge_data = hedge_data
        self.R = R

    def evaluate(self):
        raise NotImplementedError(
            f"Implement the `{type(self).__name__}.evaluate` method."
        )

    @property
    def text(self):
        t = self.valid_text if self.result else self.invalid_text
        return t % self.context


class MinLengthCondition(PlantationCondition):
    """Evaluate if there is enough hedges to plant in the project"""

    valid_text = "La longueur de la haie à planter est suffisante."
    invalid_text = """
    La longueur de la haie à planter est insuffisante.
    Elle doit être supérieure à %(minimum_length_to_plant)s m.
    """

    def evaluate(self):
        length_to_plant = self.hedge_data.length_to_plant()
        minimum_length_to_plant = self.hedge_data.length_to_remove() * self.R
        self.result = length_to_plant >= minimum_length_to_plant

        left_to_plant = max(0, minimum_length_to_plant - length_to_plant)
        self.context = {
            "length_to_plant": length_to_plant,
            "minimum_length_to_plant": round(minimum_length_to_plant),
            "left_to_plant": round(left_to_plant),
        }
        return self


class MinLengthPacCondition(PlantationCondition):

    valid_text = "Le linéaire de haie planté sur parcelle PAC est suffisant."
    invalid_text = """
    La longueur de la haie à planter sur parcelle PAC est insuffisante.
    Elle doit être supérieure à %(minimum_length_to_plant_pac)s m,
    hors alignements d’arbres.
    """

    def evaluate(self):
        # no R coefficient for PAC
        length_to_plant = self.hedge_data.length_to_plant_pac()
        minimum_length_to_plant = self.hedge_data.lineaire_detruit_pac()
        self.result = length_to_plant >= minimum_length_to_plant

        left_to_plant = max(0, minimum_length_to_plant - length_to_plant)
        self.context = {
            "minimum_length_to_plant_pac": round(minimum_length_to_plant),
            "left_to_plant_pac": round(left_to_plant),
        }
        return self


class QualityCondition(PlantationCondition):
    valid_text = "La qualité de la haie plantée est suffisante."
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


class SafetyCondition(PlantationCondition):
    valid_text = "La haie à planter ne se trouve pas sous une ligne électrique."
    invalid_text = """
        Une partie de la haie à planter, de type « alignement d'arbres » ou « haie mixte »,
        se situe sous une ligne électrique.
        Ceci doit être évité pour des raisons de sécurité.
        La haie doit être positionnée ailleurs, ou son type modifié pour ne contenir
        que des arbustes (« haie basse » ou « haie arbustive »).
    """

    def evaluate(self):
        unsafe_hedges = [
            h
            for h in self.hedge_data.hedges_to_plant()
            if h.hedge_type in ["alignement", "mixte"] and h.sous_ligne_electrique
        ]
        self.result = not unsafe_hedges
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

    def plantation_evaluate(self, R):
        hedge_data = self.catalog["haies"]
        results = [
            condition(hedge_data, R).evaluate()
            for condition in self.plantation_conditions
        ]
        return results
