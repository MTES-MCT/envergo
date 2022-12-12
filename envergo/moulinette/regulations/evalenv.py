from functools import cached_property

from django import forms
from model_utils.choices import Choices

from envergo.moulinette.regulations import MoulinetteCriterion, MoulinetteRegulation

RESULTS = Choices(
    ("systematique", "Systématique"),
    ("cas_par_cas", "Cas par cas"),
    ("non_soumis", "Non soumis"),
)


# Only ask the "emprise" question if created surface is greater or equal than
EMPRISE_THRESHOLD = 10000

# Only ask the "Zone u" question if created surface is greater or equal than
ZONE_U_THRESHOLD = 40000


class EmpriseForm(forms.Form):
    emprise = forms.IntegerField(
        label="Emprise au sol créée par le projet",
        widget=forms.TextInput,
        required=True,
    )
    zone_u = forms.ChoiceField(
        label="Le projet se situe-t-il en Zone U ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        created_surface = int(self.data["created_surface"])

        if created_surface < ZONE_U_THRESHOLD:
            del self.fields["zone_u"]

        if created_surface < EMPRISE_THRESHOLD:
            del self.fields["emprise"]


class Emprise(MoulinetteCriterion):
    slug = "emprise"
    title = "Emprise au sol créée"
    choice_label = "Éval Env > Emprise"
    subtitle = "Seuil réglementaire : 4 ha (cas par cas : 1 ha)"
    header = ""
    form_class = EmpriseForm

    def get_catalog_data(self):
        data = {}
        return data

    @property
    def result_code(self):
        """Return the unique result code"""
        return RESULTS.systematique

    @cached_property
    def result(self):
        """Run the check for the 3.3.1.0 rule.

        Associate a unique result code with a value from the RESULTS enum.
        """

        code = self.result_code
        result_matrix = {
            "systematique": RESULTS.systematique,
        }
        result = result_matrix[code]
        return result


class EvalEnvironnementale(MoulinetteRegulation):
    slug = "eval_env"
    title = "Évaluation Environnementale"
    criterion_classes = [Emprise]

    @cached_property
    def result(self):
        results = [criterion.result for criterion in self.criterions]

        if RESULTS.systematique in results:
            result = RESULTS.systematique
        elif RESULTS.cas_par_cas in results:
            result = RESULTS.cas_par_cas
        else:
            result = RESULTS.non_soumis

        return result
