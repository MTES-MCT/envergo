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


class OptionalFormMixin:
    @property
    def prefixed_cleaned_data(self):
        """Return cleaned data but use prefixed keys.

        During the evaluation, the moulinette injects all criteria's cleaned data in
        the moulinette catalog.

        When we use prefixed form, it can cause conflicts since cleaned_data uses
        non-prefixed field names, but we need each field name to be unique in the
        global catalog.
        """
        data = self.cleaned_data
        prefixed = {}
        for key, val in data.items():
            prefixed[self.add_prefix(key)] = val

        return prefixed

    def is_activated(self):
        """Did the user checked the "activate" checkbox?"""

        return self.is_bound and self.cleaned_data.get("activate", False)


class RoutesForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_06"

    activate = forms.BooleanField(
        label="Rubrique 6 : routes",
        required=True,
        widget=forms.CheckboxInput,
    )
    route_publique = forms.ChoiceField(
        label="Route publique",
        help_text="""
            Construite, élargie, ou rétrocédée au domaine public.
            Cumul autorisé depuis le 16 mai 2017
        """,
        choices=(
            ("aucune", "Aucune"),
            ("lt_10km", "< 10km (dès le premier mètre)"),
            ("gte_10km", "≥ 10km"),
        ),
        widget=forms.RadioSelect,
        required=True,
    )
    voie_privee = forms.ChoiceField(
        label="Voie privée",
        help_text="""
            Cumul autorisé depuis le 16 mai 2017
        """,
        choices=(
            ("lt_3km", "0 à 3km"),
            ("gte_3km", "≥ 3km"),
        ),
        widget=forms.RadioSelect,
        required=True,
    )
    piste_cyclable = forms.ChoiceField(
        label="Piste cyclable ou voie verte",
        help_text="""
        Cumul autorisé depuis le 16 mai 2017
        """,
        choices=(
            ("lt_10km", "< 10km"),
            ("gte_10km", "≥ 10km"),
        ),
        widget=forms.RadioSelect,
        required=True,
    )


class RoutePublique(CriterionEvaluator):
    choice_label = "Éval Env > Route publique"
    slug = "route_publique"
    form_class = RoutesForm
    CODE_MATRIX = {
        "aucune": "non_soumis",
        "lt_10km": "cas_par_cas",
        "gte_10km": "systematique",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        result = form.cleaned_data.get("route_publique")
        return result


class VoiePrivée(CriterionEvaluator):
    choice_label = "Éval Env > Voie privée"
    slug = "voie_privee"
    form_class = RoutesForm
    CODE_MATRIX = {
        "lt_3km": "non_soumis",
        "gte_3km": "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        result = form.cleaned_data.get("voie_privee")
        return result


class PisteCyclable(CriterionEvaluator):
    choice_label = "Éval Env > Piste cyclable"
    slug = "piste_cyclable"
    form_class = RoutesForm
    CODE_MATRIX = {
        "lt_10km": "non_soumis",
        "gte_10km": "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        result = form.cleaned_data.get("piste_cyclable")
        return result


class PhotovoltaiqueForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_30"

    activate = forms.BooleanField(
        label="Rubrique 30 : photovoltaïque",
        required=True,
        widget=forms.CheckboxInput,
    )
    puissance = forms.ChoiceField(
        label="Puissance",
        help_text="Cumul autorisé depuis le 16 mai 2017",
        choices=(
            ("lt_300kWc", "< 300 kWc"),
            ("300_1000kWc", "300 à 1000 kWc"),
            ("gte_1000kWc", "≥ 1000 kWc"),
        ),
        widget=forms.RadioSelect,
        required=True,
    )
    localisation = forms.ChoiceField(
        label="Localisation des panneaux",
        choices=(
            ("sol", "Au sol, y compris agrivoltaïsme"),
            ("aire_arti", "Sur aire de stationnement artificialisée"),
            ("aire_non_arti", "Sur aire de stationnement non artificialisée"),
            ("batiment_clos", "Sur bâtiment 4 murs clos ou serre ou hangar"),
            ("batiment_ouvert", "Sur bâtiment en partie ouvert"),
            ("aucun", "Aucun panneau"),
        ),
        widget=forms.RadioSelect,
        required=True,
    )


class Photovoltaique(CriterionEvaluator):
    choice_label = "Éval Env > Photovoltaïque"
    slug = "photovoltaique"
    form_class = PhotovoltaiqueForm
    CODE_MATRIX = {
        ("lt_300kWc", "sol"): "non_soumis",
        ("lt_300kWc", "aire_arti"): "non_soumis",
        ("lt_300kWc", "aire_non_arti"): "non_soumis",
        ("lt_300kWc", "batiment_clos"): "non_soumis",
        ("lt_300kWc", "batiment_ouvert"): "non_soumis",
        ("lt_300kWc", "aucun"): "non_soumis",
        ("300_1000kWc", "sol"): "cas_par_cas_sol",
        ("300_1000kWc", "aire_arti"): "non_soumis_ombriere",
        ("300_1000kWc", "aire_non_arti"): "cas_par_cas_sol",
        ("300_1000kWc", "batiment_clos"): "non_soumis_toiture",
        ("300_1000kWc", "batiment_ouvert"): "cas_par_cas_toiture",
        ("300_1000kWc", "aucun"): "non_soumis",
        ("gte_1000kWc", "sol"): "systematique_sol",
        ("gte_1000kWc", "aire_arti"): "non_soumis_ombriere",
        ("gte_1000kWc", "aire_non_arti"): "systematique_sol",
        ("gte_1000kWc", "batiment_clos"): "non_soumis_toiture",
        ("gte_1000kWc", "batiment_ouvert"): "systematique_toiture",
        ("gte_1000kWc", "aucun"): "non_soumis",
    }
    RESULT_MATRIX = {
        "non_soumis_ombriere": "non_soumis",
        "non_soumis_toiture": "non_soumis",
        "cas_par_cas_sol": "cas_par_cas",
        "cas_par_cas_toiture": "cas_par_cas",
        "systematique_sol": "systematique",
        "systematique_toiture": "systematique",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        puissance = form.cleaned_data.get("puissance")
        localisation = form.cleaned_data.get("localisation")
        return puissance, localisation


class AireDeStationnementForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_41"

    activate = forms.BooleanField(
        label="Rubrique 41 : aires de stationnement",
        required=True,
        widget=forms.CheckboxInput,
    )
    nb_emplacements = forms.ChoiceField(
        label="Nombre d'emplacements ouverts au public",
        help_text="""
            Cumul autorisé après le 16 mai 2017
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ("0_49", "De 0 à 49"),
            ("gte_50", "50 et plus"),
        ),
    )


class AireDeStationnement(CriterionEvaluator):
    choice_label = "Éval Env > Aire de stationnement"
    slug = "aire_de_stationnement"
    form_class = AireDeStationnementForm
    CODE_MATRIX = {
        "0_49": "non_soumis",
        "gte_50": "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        nb_emplacements = form.cleaned_data.get("nb_emplacements")
        return nb_emplacements


class CampingForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_42"

    activate = forms.BooleanField(
        label="Rubrique 42 : camping",
        required=True,
        widget=forms.CheckboxInput,
    )
    nb_emplacements = forms.ChoiceField(
        label="Nombre d'emplacements",
        help_text="""
            De tentes, caravanes, résidences mobiles ou habitations légères de loisirs.
            Cumul autorisé après le 16 mai 2017.
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ("0_6", "De 0 à 6"),
            ("7_199", "De 7 à 199"),
            ("gte_200", "200 et plus"),
        ),
    )


class Camping(CriterionEvaluator):
    choice_label = "Éval Env > Camping"
    slug = "camping"
    form_class = CampingForm
    CODE_MATRIX = {
        "0_6": "non_soumis",
        "7_199": "cas_par_cas",
        "gte_200": "systematique",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        nb_emplacements = form.cleaned_data.get("nb_emplacements")
        return nb_emplacements


class EquipementSportifForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_44"

    activate = forms.BooleanField(
        label="Rubrique 42 : sport / loisirs / culture",
        required=True,
        widget=forms.CheckboxInput,
    )
    nature = forms.ChoiceField(
        label="Nature du projet",
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ("sport", "Équipement sportif"),
            ("loisir", "Parc de loisirs"),
            ("culture", "Équipement culturel"),
            ("autre", "Autre"),
        ),
    )


class EquipementSportif(CriterionEvaluator):
    choice_label = "Éval Env > Equipement sportif"
    slug = "sport_loisir_culture"
    form_class = EquipementSportifForm
    CODE_MATRIX = {
        "sport": "non_soumis",
        "loisir": "cas_par_cas",
        "culture": "cas_par_cas",
        "autre": "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        nature = form.cleaned_data.get("nature")
        return nature


class DefrichementBoisementForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_47"

    activate = forms.BooleanField(
        label="Rubrique 47 : défrichement / boisement",
        required=True,
        widget=forms.CheckboxInput,
    )
    defrichement_deboisement = forms.ChoiceField(
        label="Défrichement ou déboisement",
        help_text="""
            Superficie totale, même fragmentée. Cumul autorisé après le 16 mai 2017.
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ("lt_05ha", "< 0,5 ha"),
            ("gte_05ha", "≥ 0,5 ha"),
        ),
    )
    premier_boisement = forms.ChoiceField(
        label="Premier boisement",
        help_text="""
            Ne concerne pas le reboisement d'une parcelle antérieurement à l'état boisé.
             Superficie totale, même fragmentée. Cumul autorisé après le 16 mai 2017.
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ("lt_05ha", "< 0,5 ha"),
            ("gte_05ha", "≥ 0,5 ha"),
        ),
    )


class DefrichementDeboisement(CriterionEvaluator):
    choice_label = "Éval Env > Défrichement ou déboisement"
    slug = "defrichement_deboisement"
    form_class = DefrichementBoisementForm
    CODE_MATRIX = {
        "lt_05ha": "non_soumis",
        "gte_05ha": "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        defrichement_deboisement = form.cleaned_data.get("defrichement_deboisement")
        return defrichement_deboisement


class PremierBoisement(CriterionEvaluator):
    choice_label = "Éval Env > Premier boisement"
    slug = "premier_boisement"
    form_class = DefrichementBoisementForm
    CODE_MATRIX = {
        "lt_05ha": "non_soumis",
        "gte_05ha": "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        premier_boisement = form.cleaned_data.get("premier_boisement")
        return premier_boisement


class OtherCriteria(CriterionEvaluator):
    choice_label = "Éval Env > Autres rubriques"
    slug = "autres_rubriques"

    CODES = ["non_disponible"]

    def evaluate(self):
        self._result_code, self._result = RESULTS.non_disponible, RESULTS.non_disponible
