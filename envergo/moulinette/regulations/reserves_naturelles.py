from django import forms

from envergo.hedges.models import HedgeCategory
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class ReservesNaturellesRegulation(HaieRegulationEvaluator):
    choice_label = "Haie > Réserves naturelles"

    PROCEDURE_TYPE_MATRIX = {
        "soumis_autorisation": "autorisation",
        "soumis_declaration": "declaration",
        "non_concerne": "declaration",
    }


class ReservesNaturellesForm(forms.Form):
    plan_gestion = forms.ChoiceField(
        label="La destruction de haies est-elle prévue dans le plan de gestion de la réserve naturelle où elle se "
        "situe ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )


class ReservesNaturellesRu(HaieCriterionEvaluator):
    choice_label = "Réserves naturelles > Réserves naturelles"
    base_slug = "reserves_naturelles"
    category = HedgeCategory.ru
    form_class = ReservesNaturellesForm

    CODE_MATRIX = {
        "oui": "soumis_declaration",
        "non": "soumis_autorisation",
    }

    def get_result_data(self):
        plan_gestion = self.catalog["plan_gestion"]
        return plan_gestion


class ReservesNaturellesHru(ReservesNaturellesRu):
    category = HedgeCategory.hru


class ReservesNaturellesL3503(ReservesNaturellesRu):
    category = HedgeCategory.l350_3
