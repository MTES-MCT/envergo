from django import forms

from envergo.moulinette.regulations import CriterionEvaluator


class ReservesNaturellesForm(forms.Form):
    plan_gestion = forms.ChoiceField(
        label="La destruction de haies est-elle prévue dans le plan de gestion de la réserve naturelle où elle se "
        "situe ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )


class ReservesNaturelles(CriterionEvaluator):
    choice_label = "Réserves naturelles > Réserves naturelles"
    slug = "reserves_naturelles"
    form_class = ReservesNaturellesForm

    CODE_MATRIX = {
        "oui": "soumis_declaration",
        "non": "soumis_autorisation",
    }

    def get_result_data(self):
        plan_gestion = self.catalog["plan_gestion"]
        return plan_gestion
