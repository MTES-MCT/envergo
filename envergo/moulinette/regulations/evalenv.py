from django import forms
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms.fields import (
    DisplayChoiceField,
    DisplayIntegerField,
    extract_choices,
    extract_display_function,
)
from envergo.moulinette.regulations import CriterionEvaluator

# Only ask the "emprise" question if final surface is greater or equal than
EMPRISE_THRESHOLD = 10000

# Only ask the "Zone u" question if final surface is greater or equal than
ZONE_U_THRESHOLD = 40000


class EmpriseForm(forms.Form):
    emprise = DisplayIntegerField(
        label="Emprise au sol totale",
        help_text="Projection verticale du volume de la construction, en comptant l'existant",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        required=True,
        display_unit="m²",
        display_label="Emprise totale au sol, y compris l'existant :",
        display_help_text="Projection verticale du volume de la construction",
    )
    zone_u = DisplayChoiceField(
        label=mark_safe(
            "Le projet se situe-t-il en zone U dans le <abbr title='Plan local d’urbanisme'>PLU</abbr> ?"
        ),
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
        display_label="Zonage du projet :",
        get_display_value=lambda value: (
            "Zone urbaine du PLU" if value == "oui" else "Hors zone Urbaine du PLU"
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        final_surface = int(self.data["final_surface"])
        if final_surface < ZONE_U_THRESHOLD:
            del self.fields["zone_u"]

        if final_surface < EMPRISE_THRESHOLD:
            del self.fields["emprise"]


class Emprise(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 39 (emprise)"
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
    surface_plancher_sup_thld = DisplayChoiceField(
        label="Surface de plancher totale",
        help_text="En comptant l'existant. Cumul autorisé depuis le 16 mai 2017",
        widget=forms.RadioSelect,
        choices=(
            ("oui", "Supérieure ou égale à 10 000 m2"),
            ("non", "Inférieure à 10 000 m2"),
        ),
        required=True,
        display_label="Surface de plancher totale, y compris l'existant :",
        display_help_text="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        final_surface = int(self.data["final_surface"])
        if final_surface < SURFACE_PLANCHER_THRESHOLD:
            del self.fields["surface_plancher_sup_thld"]


class SurfacePlancher(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 39 (surface plancher)"
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
    terrain_assiette = DisplayIntegerField(
        label="Terrain d'assiette du projet",
        help_text="Ensemble des parcelles cadastrales concernées par le projet",
        widget=forms.TextInput(attrs={"placeholder": _("In square meters")}),
        required=True,
        display_unit="m²",
        display_label="Surface du terrain d'assiette du projet :",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        final_surface = int(self.data["final_surface"])
        if final_surface < TERRAIN_ASSIETTE_QUESTION_THRESHOLD:
            del self.fields["terrain_assiette"]


class TerrainAssiette(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 39 (terrain d'assiette)"
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


ROUTE_PUBLIQUE_CHOICES = (
    ("aucune", "Aucune", "Aucun"),
    ("lt_10km", "< 10 km (dès le premier mètre)", "Inférieur à 10 km"),
    ("gte_10km", "≥ 10 km", "Supérieur à 10 km"),
)

VOIE_PRIVEE_CHOICES = (
    ("lt_3km", "Aucune ou < 3 km", "Aucune ou de longueur inférieure à 3 km"),
    ("gte_3km", "≥ 3 km", "Longueur supérieure à 3 km"),
)

PISTE_CYCLABLE_CHOICES = (
    ("lt_10km", "Aucune ou < 10 km", "Aucune ou de longueur inférieure à 10 km"),
    ("gte_10km", "≥ 10 km", "Longueur supérieure à 10 km"),
)


class RoutesForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_06"

    activate = forms.BooleanField(
        label="Rubrique 6 : routes",
        required=True,
        widget=forms.CheckboxInput,
    )
    route_publique = DisplayChoiceField(
        label="Route publique",
        help_text="""
            Construite, élargie, ou rétrocédée au domaine public.
            Cumul autorisé depuis le 16 mai 2017
        """,
        choices=extract_choices(ROUTE_PUBLIQUE_CHOICES),
        widget=forms.RadioSelect,
        required=True,
        display_label="Tronçon de route publique :",
        display_help_text="Construit, élargi ou rétrocédé au domaine public",
        get_display_value=extract_display_function(ROUTE_PUBLIQUE_CHOICES),
    )
    voie_privee = DisplayChoiceField(
        label="Voie privée",
        help_text="""
            Cumul autorisé depuis le 16 mai 2017
        """,
        choices=extract_choices(VOIE_PRIVEE_CHOICES),
        widget=forms.RadioSelect,
        required=True,
        display_help_text="",
        get_display_value=extract_display_function(VOIE_PRIVEE_CHOICES),
    )
    piste_cyclable = DisplayChoiceField(
        label="Piste cyclable ou voie verte",
        help_text="""
        Cumul autorisé depuis le 16 mai 2017
        """,
        choices=extract_choices(PISTE_CYCLABLE_CHOICES),
        widget=forms.RadioSelect,
        required=True,
        display_help_text="",
        get_display_value=extract_display_function(PISTE_CYCLABLE_CHOICES),
    )


class RoutePublique(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 6 (route publique)"
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


class VoiePrivee(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 6 (voie privée)"
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
    choice_label = "Éval Env > Rubrique 6 (piste cyclable)"
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


PUISSANCE_CHOICES = (
    ("lt_300kWc", "< 300 kWc", "Inférieure à 300 kWc"),
    ("300_1000kWc", "300 à 1000 kWc", "Entre 300 kWc et 1 000 kWc"),
    ("gte_1000kWc", "≥ 1000 kWc", "Supérieure à 1 000 kWc"),
)

LOCALISATION_CHOICES = (
    ("sol", "Au sol, y compris agrivoltaïsme"),
    ("aire_arti", "Sur aire de stationnement artificialisée"),
    ("aire_non_arti", "Sur aire de stationnement non artificialisée"),
    ("batiment_clos", "Sur bâtiment 4 murs clos ou serre ou hangar"),
    ("batiment_ouvert", "Sur bâtiment en partie ouvert"),
    ("aucun", "Aucun panneau"),
)


class PhotovoltaiqueForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_30"

    activate = forms.BooleanField(
        label="Rubrique 30 : photovoltaïque",
        required=True,
        widget=forms.CheckboxInput,
    )
    puissance = DisplayChoiceField(
        label="Puissance",
        help_text="Cumul autorisé depuis le 16 mai 2017",
        choices=extract_choices(PUISSANCE_CHOICES),
        widget=forms.RadioSelect,
        required=True,
        display_help_text="",
        display_label="Puissance photovoltaïque :",
        get_display_value=extract_display_function(PUISSANCE_CHOICES),
    )
    localisation = DisplayChoiceField(
        label="Localisation des panneaux",
        choices=LOCALISATION_CHOICES,
        widget=forms.RadioSelect,
        required=True,
        display_label="Localisation des panneaux photovoltaïques :",
        get_display_value=lambda value: (
            "Au sol" if value == "sol" else dict(LOCALISATION_CHOICES).get(value, value)
        ),
    )


class Photovoltaique(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 30 (PV)"
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


TYPE_STATIONNEMENT_CHOICES = (
    ("public", "Ouvert au public", "Ouverte au public"),
    ("private", "Privé", "Privée"),
    ("mixed", "Mixte", "Mixte public-privé (au moins une place est ouverte au public)"),
)

NB_EMPLACEMENTS_CHOICES = (
    ("0_49", "De 0 à 49", "0 à 49"),
    ("gte_50", "50 et plus", "50 ou plus"),
)


class AireDeStationnementForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_41"

    activate = forms.BooleanField(
        label="Rubrique 41 : aires de stationnement",
        required=True,
        widget=forms.CheckboxInput,
    )
    type_stationnement = DisplayChoiceField(
        label="Type de stationnement",
        help_text="""
            Privé : attaché à des logements ou réservé à des employés.
            Mixte : si au moins une place est ouverte au public
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=extract_choices(TYPE_STATIONNEMENT_CHOICES),
        display_help_text="",
        display_label="Aire de stationnement :",
        get_display_value=extract_display_function(TYPE_STATIONNEMENT_CHOICES),
    )
    nb_emplacements = DisplayChoiceField(
        label="Nombre total d'emplacements",
        help_text="""
            Somme des places privées et publiques.
            Cumul autorisé après le 16 mai 2017
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=extract_choices(NB_EMPLACEMENTS_CHOICES),
        display_help_text="Somme des places privées et publiques",
        display_label="Nombre total d'emplacements de stationnement :",
        get_display_value=extract_display_function(NB_EMPLACEMENTS_CHOICES),
    )


class AireDeStationnement(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 41 (stationnement)"
    slug = "aire_de_stationnement"
    form_class = AireDeStationnementForm
    CODE_MATRIX = {
        ("0_49", "private"): "non_soumis",
        ("gte_50", "private"): "non_soumis",
        ("0_49", "mixed"): "non_soumis",
        ("gte_50", "mixed"): "cas_par_cas",
        ("0_49", "public"): "non_soumis",
        ("gte_50", "public"): "cas_par_cas",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        nb_emplacements = form.cleaned_data.get("nb_emplacements")
        type_stationnement = form.cleaned_data.get("type_stationnement")
        return nb_emplacements, type_stationnement


NB_EMPLACEMENTS_CAMPING_CHOICES = (
    ("0_6", "De 0 à 6", "De 0 à 6 emplacements"),
    ("7_199", "De 7 à 199", "De 7 à 199 emplacements"),
    ("gte_200", "200 et plus", "200 emplacements ou plus"),
)


class CampingForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_42"

    activate = forms.BooleanField(
        label="Rubrique 42 : camping",
        required=True,
        widget=forms.CheckboxInput,
    )
    nb_emplacements = DisplayChoiceField(
        label="Nombre d'emplacements",
        help_text="""
            De tentes, caravanes, résidences mobiles ou habitations légères de loisirs.
            Cumul autorisé après le 16 mai 2017.
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=extract_choices(NB_EMPLACEMENTS_CAMPING_CHOICES),
        display_help_text="Tentes, caravanes, résidences mobiles ou habitations légères de loisirs",
        display_label="Terrain de camping :",
        get_display_value=extract_display_function(NB_EMPLACEMENTS_CAMPING_CHOICES),
    )


class Camping(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 42 (camping)"
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


TYPE_EQUIPEMENT_CHOICES = (
    ("sport", "Équipement sportif"),
    ("loisir", "Parc de loisirs"),
    ("culture", "Équipement culturel"),
    ("autre", "Autre (hors nomenclature)"),
)


class EquipementSportifForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_44"

    activate = forms.BooleanField(
        label="Rubrique 44 : sport / loisirs / culture",
        required=True,
        widget=forms.CheckboxInput,
    )
    type = DisplayChoiceField(
        label="Type d'équipement",
        required=True,
        widget=forms.RadioSelect,
        choices=TYPE_EQUIPEMENT_CHOICES,
        get_display_value=lambda value: (
            "Ni sportif, ni de loisirs, ni culturel"
            if value == "autre"
            else dict(TYPE_EQUIPEMENT_CHOICES).get(value, value)
        ),
    )
    capacite_accueil = forms.ChoiceField(
        label="Capacité d'accueil",
        required=True,
        widget=forms.RadioSelect,
        choices=(
            ("lt_1000", "0 à 999 personnes"),
            ("gte_1000", "1000 personnes ou plus"),
        ),
    )


class EquipementSportif(CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 44 (équipement sportif)"
    slug = "sport_loisir_culture"
    form_class = EquipementSportifForm
    CODE_MATRIX = {
        ("lt_1000", "autre"): "non_soumis",
        ("gte_1000", "autre"): "non_soumis",
        ("lt_1000", "sport"): "non_soumis_lt1000",
        ("lt_1000", "loisir"): "non_soumis_lt1000",
        ("lt_1000", "culture"): "non_soumis_lt1000",
        ("gte_1000", "sport"): "cas_par_cas",
        ("gte_1000", "loisir"): "cas_par_cas",
        ("gte_1000", "culture"): "cas_par_cas",
    }
    RESULT_MATRIX = {
        "non_soumis_lt1000": "non_soumis",
    }

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        capacite_accueil = form.cleaned_data.get("capacite_accueil")
        type = form.cleaned_data.get("type")
        return capacite_accueil, type


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
            Uniquement en cas de changement de destination du terrain.
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
    choice_label = "Éval Env > Rubrique 47 (déboisement)"
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
    choice_label = "Éval Env > Rubrique 47 (premier boisement)"
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

    def should_be_displayed(self):
        optional_criteria = self.moulinette.eval_env.get_optional_criteria()
        return not bool(optional_criteria)
