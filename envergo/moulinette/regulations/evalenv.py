from django import forms
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.regulations import CriterionEvaluator

# Only ask the "emprise" question if final surface is greater or equal than
EMPRISE_THRESHOLD = 10000

# Only ask the "Zone u" question if final surface is greater or equal than
ZONE_U_THRESHOLD = 40000


class EmpriseForm(forms.Form):
    emprise = forms.IntegerField(
        label="Emprise au sol totale",
        help_text="Projection verticale du volume de la construction, en comptant l'existant",
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

        final_surface = int(self.data["final_surface"])
        if final_surface < ZONE_U_THRESHOLD:
            del self.fields["zone_u"]

        if final_surface < EMPRISE_THRESHOLD:
            del self.fields["emprise"]


class Emprise(CriterionEvaluator):
    choice_label = "Éval Env > Emprise"
    slug = "emprise"
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
        final_surface = self.catalog.get("final_surface", 0)
        if emprise >= ZONE_U_THRESHOLD and final_surface >= ZONE_U_THRESHOLD:
            surface = "40000"
        elif emprise >= EMPRISE_THRESHOLD and final_surface >= EMPRISE_THRESHOLD:
            surface = "10000"
        else:
            surface = "0"

        zone_u = self.catalog.get("zone_u", "non")
        return surface, zone_u


SURFACE_PLANCHER_THRESHOLD = 3000


class SurfacePlancherForm(forms.Form):
    surface_plancher_sup_thld = forms.ChoiceField(
        label="La surface de plancher totale sera-t-elle supérieure à 10 000 m² ?",
        help_text="En comptant l'existant",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        final_surface = int(self.data["final_surface"])
        if final_surface < SURFACE_PLANCHER_THRESHOLD:
            del self.fields["surface_plancher_sup_thld"]


class SurfacePlancher(CriterionEvaluator):
    choice_label = "Éval Env > Surface Plancher"
    slug = "surface_plancher"
    form_class = SurfacePlancherForm

    CODES = ["cas_par_cas", "non_soumis", "non_disponible"]

    CODE_MATRIX = {
        "non": "non_soumis",
        "oui": "cas_par_cas",
    }

    def get_result_data(self):
        surface_plancher_sup_thld = self.catalog.get("surface_plancher_sup_thld", "non")
        return surface_plancher_sup_thld


TERRAIN_ASSIETTE_QUESTION_THRESHOLD = 10000
TERRAIN_ASSIETTE_CASPARCAS_THRESHOLD = 50000
TERRAIN_ASSIETTE_SYSTEMATIQUE_THRESHOLD = 100000


class TerrainAssietteForm(forms.Form):
    terrain_assiette = forms.IntegerField(
        label="Terrain d'assiette du projet",
        help_text="Ensemble des parcelles cadastrales concernées par le projet",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        final_surface = int(self.data["final_surface"])
        if final_surface < TERRAIN_ASSIETTE_QUESTION_THRESHOLD:
            del self.fields["terrain_assiette"]


class TerrainAssiette(CriterionEvaluator):
    choice_label = "Éval Env > Terrain d'assiette"
    slug = "terrain_assiette"
    form_class = TerrainAssietteForm

    CODES = ["systematique", "cas_par_cas", "non_soumis", "non_concerne"]

    CODE_MATRIX = {
        "10000": "non_soumis",
        "50000": "cas_par_cas",
        "100000": "systematique",
    }

    def get_result_data(self):
        terrain_assiette = self.catalog.get("terrain_assiette", 0)

        if terrain_assiette >= TERRAIN_ASSIETTE_SYSTEMATIQUE_THRESHOLD:
            assiette_thld = "100000"
        elif terrain_assiette >= TERRAIN_ASSIETTE_CASPARCAS_THRESHOLD:
            assiette_thld = "50000"
        else:
            assiette_thld = "10000"
        return assiette_thld


class AireDeStationnementForm(forms.Form):
    evalenv_rubrique_41_soumis = forms.ChoiceField(
        label="Rubrique 41 : aires de stationnement",
        required=True,
        help_text="""Seuil du cas par cas : plus de 50 places ouvertes au public
                     (construites après le 16 mai 2017)
        """,
        widget=forms.RadioSelect,
        choices=(("oui", "Soumis"), ("non", "Non soumis")),
    )


class AireDeStationnement(CriterionEvaluator):
    choice_label = "Éval Env > Aire de stationnement"
    slug = "aire_de_stationnement"
    form_class = AireDeStationnementForm
    CODE_MATRIX = {
        "oui": "cas_par_cas",
        "non": "non_soumis",
    }

    def get_result_data(self):
        soumis = self.catalog.get("rubrique_41_soumis")
        return soumis


class OtherCriteria(CriterionEvaluator):
    choice_label = "Éval Env > Autres rubriques"
    slug = "autres_rubriques"

    CODES = ["non_disponible"]

    def evaluate(self):
        self._result_code, self._result = RESULTS.non_disponible, RESULTS.non_disponible
