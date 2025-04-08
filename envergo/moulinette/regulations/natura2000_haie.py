from django import forms

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator


class Natura2000HaieSettings(forms.Form):
    result = forms.ChoiceField(
        label="Resultat attendu de l'évaluateur",
        help_text="Indique si l’arrachage de haies est soumis à évaluation des incidences Natura 2000 pour ce critère.",
        required=True,
        choices=RESULTS,
    )


class Natura2000Haie(CriterionEvaluator):
    choice_label = "Natura 2000 > Haie"
    slug = "natura2000_haie"
    settings_form_class = Natura2000HaieSettings

    CODE_MATRIX = {
        "soumis": "soumis",
        "non_soumis": "non_soumis",
    }

    RESULT_MATRIX = {
        "non_soumis": RESULTS.non_soumis,
        "soumis": RESULTS.soumis,
    }

    def get_result_data(self):
        return self.settings.get("result", "non_soumis")
