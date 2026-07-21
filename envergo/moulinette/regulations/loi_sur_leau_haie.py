from django import forms
from django.utils.safestring import mark_safe

from envergo.evaluations.models import RESULTS
from envergo.hedges.models import HedgeCategory
from envergo.moulinette.forms import (
    DisplayChoiceField,
    extract_choices,
    extract_display_function,
)
from envergo.moulinette.regulations import (
    HaieCriterionEvaluator,
    HaieRegulationEvaluator,
)


class LoiSurLeauHaieRegulation(HaieRegulationEvaluator):
    """Evaluate the loi sur l'eau (haie) regulation."""

    choice_label = "Haie > Loi sur l'eau"

    PROCEDURE_TYPE_MATRIX = {
        "a_verifier": "declaration",
        "soumis": "declaration",
        "non_soumis": "declaration",
        "non_concerne": "declaration",
    }


TECHNIQUE_CONSOLIDATION_CHOICES = (
    ("non", "Pas de consolidation des berges", "Pas de travaux de consolidation"),
    (
        "vegetale",
        mark_safe(
            "Par des techniques végétales vivantes"
            '<span class="fr-hint-text">Bouturage, plançons, fascines, garnissage,'
            " boudins de pré-végétalisé</span>"
        ),
        "Par des techniques végétales vivantes",
    ),
    (
        "autre",
        "Par d’autres techniques",
        "Par des techniques autres que végétales vivantes",
    ),
)


class LoiSurLeauHaieRuForm(forms.Form):
    """Complementary question about ripisylves."""

    travaux_berges = forms.ChoiceField(
        label="La destruction des haies ripisylves intervient-elle dans le cadre de travaux de consolidation ou"
        " de protection des berges ?",
        widget=forms.RadioSelect,
        choices=(
            ("non", "Non"),
            (
                "cours_eau",
                "Oui, des berges d’un cours d’eau",
            ),
            (
                "hors_cours_eau",
                "Oui, mais uniquement des berges d’un plan d’eau ou d’un canal artificiel",
            ),
        ),
        required=True,
    )

    technique_consolidation = DisplayChoiceField(
        label="S’il s’agit de travaux de consolidation ou de protection des berges, comment sont-ils réalisés ?",
        widget=forms.RadioSelect,
        required=True,
        choices=extract_choices(TECHNIQUE_CONSOLIDATION_CHOICES),
        get_display_value=extract_display_function(TECHNIQUE_CONSOLIDATION_CHOICES),
    )

    def clean(self):
        cleaned_data = super().clean()
        travaux_berges = cleaned_data.get("travaux_berges")
        technique_consolidation = cleaned_data.get("technique_consolidation")
        if travaux_berges == "non" and technique_consolidation != "non":
            self.add_error(
                "travaux_berges",
                "Le choix « Non » est incompatible avec la réponse plus bas qui indique qu’il s’agit de "
                "travaux de consolidation ou de protection des berges. Modifier l’une ou l’autre des réponses.",
            )
        elif travaux_berges != "non" and technique_consolidation == "non":
            self.add_error(
                "technique_consolidation",
                " Le choix « Pas de consolidation des berges » est incompatible avec la réponse plus haut "
                "qui indique qu’il s’agit de travaux de consolidation ou de protection des berges. Modifier l’une ou "
                "l’autre des réponses.",
            )
        return cleaned_data


class LoiSurLeauHaieHru(HaieCriterionEvaluator):
    """Evaluate the loi sur l'eau (haie) criterion."""

    choice_label = "Loi sur l'eau Haie > Loi sur l'eau Haie"
    base_slug = "loi_sur_leau_haie"
    plantation_conditions = []
    category = HedgeCategory.hru

    RESULT_MATRIX = {
        "a_verifier": RESULTS.a_verifier,
        "non_concerne": RESULTS.non_concerne,
    }

    CODE_MATRIX = {
        True: "a_verifier",
        False: "non_concerne",
    }

    def get_result_data(self):
        if self.hedges.prop("ripisylve").length:
            return True

        return False


class LoiSurLeauHaieL3503(LoiSurLeauHaieHru):
    category = HedgeCategory.l350_3


class LoiSurLeauHaieRu(LoiSurLeauHaieHru):
    category = HedgeCategory.ru
    form_class = LoiSurLeauHaieRuForm

    RESULT_MATRIX = {
        "soumis": RESULTS.soumis,
        "non_soumis": RESULTS.non_soumis,
        "non_concerne": RESULTS.non_concerne,
    }

    def get_form_class(self):
        """Skip the ripisylve questions when no ripisylve hedge is being removed."""
        if not self.hedges.to_remove().prop("ripisylve").length:
            return None
        return super().get_form_class()

    CODE_MATRIX = {
        ("destruction_ripisylve", "autre_travaux_sur_cours_d_eau"): "soumis",
        ("pas_de_destruction", "autre_travaux_sur_cours_d_eau"): "non_concerne",
        ("destruction_ripisylve", "travaux_peu_impactant"): "non_soumis",
        ("pas_de_destruction", "travaux_peu_impactant"): "non_concerne",
    }

    def get_result_data(self):
        destruction_ripisylve = bool(self.hedges.to_remove().prop("ripisylve").length)
        autre_travaux_sur_cours_d_eau = (
            self.catalog.get("travaux_berges") == "cours_eau"
            and self.catalog.get("technique_consolidation") == "autre"
        )

        return (
            "destruction_ripisylve" if destruction_ripisylve else "pas_de_destruction",
            (
                "autre_travaux_sur_cours_d_eau"
                if autre_travaux_sur_cours_d_eau
                else "travaux_peu_impactant"
            ),
        )
