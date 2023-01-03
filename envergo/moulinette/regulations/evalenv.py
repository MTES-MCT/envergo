from functools import cached_property

from django import forms
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from model_utils.choices import Choices

from envergo.moulinette.regulations import MoulinetteCriterion, MoulinetteRegulation

RESULTS = Choices(
    ("systematique", "Soumis"),
    ("cas_par_cas", "Cas par cas"),
    ("non_soumis", "Non soumis"),
    ("clause_filet", "Clause filet"),
    ("non_concerne", "Non concerné"),
)


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


class Emprise(MoulinetteCriterion):
    slug = "emprise"
    title = "Emprise au sol créée"
    choice_label = "Éval Env > Emprise"
    subtitle = "Seuil réglementaire : 4 ha (cas par cas : 1 ha)"
    header = "Rubrique 39 a) de l’<a target='_blank' rel='noopener' href='https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042369329'>annexe à l’art. R122-2 du code de l’environnement</a>"
    form_class = EmpriseForm

    def get_catalog_data(self):
        data = {}
        return data

    @property
    def result_code(self):
        """Return the unique result code"""
        form = self.get_form()
        if not form.is_valid():
            return "non_disponible"

        emprise = form.cleaned_data.get("emprise", None)
        if emprise is None or emprise < EMPRISE_THRESHOLD:
            result = RESULTS.non_soumis

        elif emprise >= EMPRISE_THRESHOLD and emprise < ZONE_U_THRESHOLD:
            result = RESULTS.cas_par_cas

        else:
            zone_u = form.cleaned_data.get("zone_u")
            if zone_u == "oui":
                result = RESULTS.cas_par_cas
            else:
                result = RESULTS.systematique

        return result

    @cached_property
    def result(self):
        code = self.result_code
        return code


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


class SurfacePlancher(MoulinetteCriterion):
    slug = "surface_plancher"
    title = "Surface de plancher créée"
    choice_label = "Éval Env > Surface Plancher"
    subtitle = "Seuil réglementaire : 10 000 m²"
    header = "Rubrique 39 a) de l’<a target='_blank' rel='noopener' href='https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042369329'>annexe à l’art. R122-2 du code de l’environnement</a>"
    form_class = SurfacePlancherForm

    def get_catalog_data(self):
        data = {}
        return data

    @property
    def result_code(self):
        """Return the unique result code"""
        form = self.get_form()
        if not form.is_valid():
            return "non_disponible"

        surface_plancher_sup_thld = form.cleaned_data.get(
            "surface_plancher_sup_thld", None
        )
        if surface_plancher_sup_thld is None or surface_plancher_sup_thld == "non":
            result = RESULTS.non_soumis

        else:
            result = RESULTS.cas_par_cas

        return result

    @cached_property
    def result(self):
        code = self.result_code
        return code


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

        created_surface = int(self.data["created_surface"])
        existing_surface = int(self.data["existing_surface"])
        total_surface = created_surface + existing_surface

        if total_surface < TERRAIN_ASSIETTE_THRESHOLD:
            del self.fields["terrain_assiette"]
            del self.fields["is_lotissement"]


class TerrainAssiette(MoulinetteCriterion):
    slug = "terrain_assiette"
    title = "Terrain d'assiette de l'opération"
    choice_label = "Éval Env > Terrain d'assiette"
    subtitle = "Seuil réglementaire : 10 ha (cas par cas : 5 ha)"
    header = "Rubrique 39 b) de l’<a target='_blank' rel='noopener' href='https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042369329'>annexe à l’art. R122-2 du code de l’environnement</a>"
    form_class = TerrainAssietteForm

    def get_catalog_data(self):
        data = {}
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


class ClauseFilet(MoulinetteCriterion):
    slug = "clause_filet"
    title = "Clause filet"
    choice_label = "Éval Env > Clause Filet"
    subtitle = ""
    header = ""

    @property
    def result_code(self):
        """Return the unique result code"""

        return RESULTS.clause_filet


class EvalEnvironnementale(MoulinetteRegulation):
    slug = "eval_env"
    title = "Évaluation Environnementale"
    criterion_classes = [Emprise, SurfacePlancher, TerrainAssiette]

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
