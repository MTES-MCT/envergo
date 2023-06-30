from functools import cached_property

from django import forms
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator, MoulinetteRegulation

# Only ask the "emprise" question if created surface is greater or equal than
EMPRISE_THRESHOLD = 10000

# Only ask the "Zone u" question if created surface is greater or equal than
ZONE_U_THRESHOLD = 40000


class EmpriseForm(forms.Form):
    emprise = forms.IntegerField(
        label="Emprise au sol créée par le projet",
        help_text="Projection verticale du volume de la construction nouvelle",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        required=True,
    )
    zone_u = forms.ChoiceField(
        label=mark_safe(
            "Le projet se situe-t-il en zone U dans le <abbr title='Plan local d’urbanisme'>PLU</abbr> ?"
        ),
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


class Emprise(CriterionEvaluator):
    choice_label = "Éval Env > Emprise"
    form_class = EmpriseForm

    CODES = ["systematique", "cas_par_cas", "non_soumis"]

    CODE_MATRIX = {
        ("40000", "oui"): "cas_par_cas",
        ("40000", "non"): "systematique",
        ("10000", "oui"): "cas_par_cas",
        ("10000", "non"): "cas_par_cas",
        ("0", "oui"): "non_soumis",
        ("0", "non"): "non_soumis",
    }

    def get_result_data(self):
        emprise = self.catalog.get("emprise", 0)
        if emprise >= ZONE_U_THRESHOLD:
            emprise_threshold = "40000"
        elif emprise >= EMPRISE_THRESHOLD:
            emprise_threshold = "10000"
        else:
            emprise_threshold = "0"

        zone_u = self.catalog.get("zone_u", "non")
        return emprise_threshold, zone_u


SURFACE_PLANCHER_THRESHOLD = 3000


class SurfacePlancherForm(forms.Form):
    surface_plancher_sup_thld = forms.ChoiceField(
        label="Le projet crée-t-il une surface de plancher supérieure à 10 000 m² ?",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        created_surface = int(self.data["created_surface"])

        if created_surface < SURFACE_PLANCHER_THRESHOLD:
            del self.fields["surface_plancher_sup_thld"]


class SurfacePlancher(CriterionEvaluator):
    choice_label = "Éval Env > Surface Plancher"
    form_class = SurfacePlancherForm

    CODES = ["cas_par_cas", "non_soumis", "non_disponible"]

    CODE_MATRIX = {
        "non": "non_soumis",
        "oui": "cas_par_cas",
    }

    def get_result_data(self):
        surface_plancher_sup_thld = self.catalog.get("surface_plancher_sup_thld", "non")
        return surface_plancher_sup_thld


TERRAIN_ASSIETTE_THRESHOLD = 10000


class TerrainAssietteForm(forms.Form):
    terrain_assiette = forms.IntegerField(
        label="Terrain d'assiette du projet",
        help_text="Ensemble des parcelles cadastrales concernées par le projet",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        required=True,
    )
    is_lotissement = forms.ChoiceField(
        label=_("Le projet concerne-t-il un lotissement ?"),
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.data.get("final_surface", None):
            final_surface = int(self.data["final_surface"])
        else:
            created_surface = int(self.data["created_surface"])
            existing_surface = int(self.data["existing_surface"])
            final_surface = created_surface + existing_surface

        if final_surface < TERRAIN_ASSIETTE_THRESHOLD:
            del self.fields["terrain_assiette"]
            del self.fields["is_lotissement"]


class TerrainAssiette(CriterionEvaluator):
    slug = "terrain_assiette"
    title = "Terrain d'assiette"
    choice_label = "Éval Env > Terrain d'assiette"
    subtitle = "Seuil réglementaire : 10 ha (cas par cas : 5 ha)"
    header = """Rubrique 39 b) de l’<a target='_blank' rel='noopener'
                href='https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042369329'>
                annexe à l’art. R122-2 du code de l’environnement</a>"""
    form_class = TerrainAssietteForm

    CODES = ["systematique", "cas_par_cas", "non_soumis", "non_concerne"]

    def get_catalog_data(self):
        data = super().get_catalog_data()
        return data

    @property
    def result_code(self):
        """Return the unique result code"""
        form = self.get_form()
        if not form.is_valid():
            return "non_disponible"

        is_lotissement = form.cleaned_data.get("is_lotissement", None)
        terrain_assiette = form.cleaned_data.get("terrain_assiette", None)

        if is_lotissement is None or terrain_assiette is None:
            result = RESULTS.non_soumis
        elif is_lotissement == "non":
            result = RESULTS.non_concerne
        else:
            if terrain_assiette < 50000:
                result = RESULTS.non_soumis
            elif terrain_assiette < 100000:
                result = RESULTS.cas_par_cas
            else:
                result = RESULTS.systematique

        return result

    @cached_property
    def result(self):
        code = self.result_code
        return code


class ClauseFilet(CriterionEvaluator):
    slug = "clause_filet"
    title = "Clause filet"
    choice_label = "Éval Env > Clause Filet"
    subtitle = ""
    header = ""

    @property
    def result_code(self):
        """Return the unique result code"""

        return RESULTS.clause_filet


class OtherCriteria(CriterionEvaluator):
    slug = "autres_rubriques"
    choice_label = "Éval Env > Autres rubriques"
    title = "Autres rubriques"

    CODES = ["non_disponible"]

    @cached_property
    def result_code(self):
        return RESULTS.non_disponible


class EvalEnvironnementale(MoulinetteRegulation):
    slug = "eval_env"
    title = "Évaluation Environnementale"
    criterion_classes = [Emprise, SurfacePlancher, TerrainAssiette, OtherCriteria]

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
