from django import forms
from django.utils.html import mark_safe

from envergo.evaluations.models import RESULTS
from envergo.moulinette.forms.fields import (
    DisplayChoiceField,
    DisplayIntegerField,
    UnitInput,
    extract_choices,
    extract_display_function,
)
from envergo.moulinette.regulations import (
    TO_ADD,
    TO_SUBTRACT,
    ActionsToTakeMixin,
    AmenagementRegulationEvaluator,
    CriterionEvaluator,
    SelfDeclarationMixin,
)

# Only ask the "emprise" question if final surface is greater or equal than
EMPRISE_THRESHOLD = 10000

# Only ask the "Zone u" question if final surface is greater or equal than
ZONE_U_THRESHOLD = 40000


class EvalEnvRegulation(ActionsToTakeMixin, AmenagementRegulationEvaluator):
    choice_label = "Aménagement > Eval Env"

    ACTIONS_TO_TAKE_MATRIX = {
        "systematique": {
            TO_ADD: {"depot_etude_impact", "pc_etude_impact"},
            TO_SUBTRACT: {"pc_ein"},
        },
        "cas_par_cas": {TO_ADD: {"depot_cas_par_cas", "pc_cas_par_cas"}},
    }


class EmpriseForm(forms.Form):
    emprise = DisplayIntegerField(
        label="Emprise au sol totale",
        help_text="Projection verticale du volume de la construction. "
        "Inclure l'existant autorisé depuis le 16 mai 2017.",
        widget=UnitInput(
            unit="m²", attrs={"placeholder": "8000", "inputmode": "numeric"}
        ),
        required=True,
        display_unit="m²",
        display_label="Emprise totale au sol, y compris l'existant :",
        display_help_text="Projection verticale du volume de la construction. Cumul autorisé depuis le 16 mai 2017.",
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
            "Zone urbaine du PLU" if value == "oui" else "Hors zone urbaine du PLU"
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.data else self.initial

        final_surface = int(data.get("final_surface"))
        if final_surface < ZONE_U_THRESHOLD:
            del self.fields["zone_u"]

        if final_surface < EMPRISE_THRESHOLD:
            del self.fields["emprise"]


class Emprise(SelfDeclarationMixin, CriterionEvaluator):
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
        help_text="Inclure l'existant autorisé depuis le 16 mai 2017.",
        widget=forms.RadioSelect,
        choices=(
            ("oui", "Supérieure ou égale à 10 000 m²"),
            ("non", "Inférieure à 10 000 m²"),
        ),
        required=True,
        display_label="Surface de plancher totale, y compris l'existant :",
        display_help_text="Cumul autorisé depuis le 16 mai 2017.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.data else self.initial

        final_surface = int(data.get("final_surface"))
        if final_surface < SURFACE_PLANCHER_THRESHOLD:
            del self.fields["surface_plancher_sup_thld"]


class SurfacePlancher(SelfDeclarationMixin, CriterionEvaluator):
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

    operation_amenagement = DisplayChoiceField(
        label="Le projet constitue-t-il une opération d'aménagement ?",
        help_text="Tout ensemble de constructions et travaux soumis à plusieurs permis \
            de construire ou d’aménager, par exemple création d’une ZAC ou d’un lotissement",
        widget=forms.RadioSelect,
        choices=(("oui", "Oui"), ("non", "Non")),
        required=True,
        display_label="Le projet constitue-t-il une opération d'aménagement ?",
    )

    terrain_assiette = DisplayIntegerField(
        label="Terrain d'assiette du projet",
        help_text="""Surface couverte par les aménagements du projet dans leur étendue la plus large (enveloppe convexe),
        <a href="https://www.ecologie.gouv.fr/sites/default/files/documents/%C3%89valuation%20environnementale%20des%20projets%20%E2%80%93%20Guide%20de%20lecture%20de%20la%20nomenclature.pdf"
        rel="noopener" target="_blank">voir p.&nbsp;50 du guide</a>.""",  # noqa 501
        widget=UnitInput(
            unit="m²",
            attrs={"placeholder": "8000", "inputmode": "numeric"},
        ),
        required=True,
        display_unit="m²",
        display_label="Surface du terrain d'assiette du projet :",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        data = self.data if self.data else self.initial

        final_surface = int(data.get("final_surface"))
        if final_surface < TERRAIN_ASSIETTE_QUESTION_THRESHOLD:
            del self.fields["terrain_assiette"]
            del self.fields["operation_amenagement"]


class TerrainAssiette(SelfDeclarationMixin, CriterionEvaluator):
    choice_label = "Éval Env > Rubrique 39 (terrain d'assiette)"
    slug = "terrain_assiette"
    form_class = TerrainAssietteForm

    CODES = ["systematique", "cas_par_cas", "non_soumis", "non_concerne"]

    CODE_MATRIX = {
        ("N/A", "non"): "non_concerne",
        ("10000", "oui"): "non_soumis",
        ("50000", "oui"): "cas_par_cas",
        ("100000", "oui"): "systematique",
    }

    def get_result_data(self):
        operation_amenagement = self.catalog.get("operation_amenagement", "non")

        if not operation_amenagement == "oui":
            return ("N/A", operation_amenagement)

        terrain_assiette = self.catalog.get("terrain_assiette", 0)

        if terrain_assiette >= TERRAIN_ASSIETTE_SYSTEMATIQUE_THRESHOLD:
            assiette_thld = "100000"
        elif terrain_assiette >= TERRAIN_ASSIETTE_CASPARCAS_THRESHOLD:
            assiette_thld = "50000"
        else:
            assiette_thld = "10000"
        return assiette_thld, operation_amenagement


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

    def get_initial_for_field(self, field, field_name):
        """By default, Django doesn't take prefix into account for initial fields."""

        field_name = f"{self.prefix}-{field_name}"
        return super().get_initial_for_field(field, field_name)

    def is_activated(self):
        """Did the user checked the "activate" checkbox?"""

        return self.is_bound and self.cleaned_data.get("activate", False)


ROUTE_PUBLIQUE_CHOICES = (
    ("aucune", "Aucune", "Aucune"),
    ("lt_10km", "De 0 (dès le premier mètre) à 10 km", "Moins de 10 km"),
    ("gte_10km", "10 km ou plus", "10 km ou plus"),
)

VOIE_PRIVEE_CHOICES = (
    ("lt_3km", "Aucune ou moins de 3 km"),
    ("gte_3km", "3 km ou plus"),
)

PISTE_CYCLABLE_CHOICES = (
    ("lt_10km", "Aucune ou moins de 10 km"),
    ("gte_10km", "10 km ou plus"),
)


class RoutesForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_06"

    activate = forms.BooleanField(
        label="Aménagement de voirie",
        help_text="""Rubrique 6 de l'évaluation environnementale<br>
        Cumul autorisé depuis le 16 mai 2017
        """,
        required=True,
        widget=forms.CheckboxInput,
    )
    route_publique = DisplayChoiceField(
        label="Route publique",
        help_text="""
            Construction ou élargissement d'une route publique, ou rétrocession d’une voie privée au domaine public
        """,
        choices=extract_choices(ROUTE_PUBLIQUE_CHOICES),
        widget=forms.RadioSelect,
        required=True,
        get_display_value=extract_display_function(ROUTE_PUBLIQUE_CHOICES),
    )
    voie_privee = DisplayChoiceField(
        label="Voie privée",
        help_text="""
        """,
        choices=VOIE_PRIVEE_CHOICES,
        widget=forms.RadioSelect,
        required=True,
    )
    piste_cyclable = DisplayChoiceField(
        label="Piste cyclable ou voie verte",
        help_text="""
        """,
        choices=PISTE_CYCLABLE_CHOICES,
        widget=forms.RadioSelect,
        required=True,
    )


class RoutePublique(SelfDeclarationMixin, CriterionEvaluator):
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


class VoiePrivee(SelfDeclarationMixin, CriterionEvaluator):
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


class PisteCyclable(SelfDeclarationMixin, CriterionEvaluator):
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
    ("lt_300kWc", "Moins de 300 kWc"),
    ("300_1000kWc", "Entre 300 et 1 000 kWc"),
    ("gte_1000kWc", "1 000 kWc ou plus"),
)

LOCALISATION_CHOICES = (
    ("sol", "Au sol"),
    ("aire_arti", "Ombrière sur une aire de stationnement artificialisée"),
    (
        "aire_non_arti",
        {
            "label": "Ombrière autre",
            "help_text": "Sur sol agricole, aire de stationnement non artificialisée…",
        },
    ),
    (
        "batiment_clos",
        {
            "label": "Toiture d’un hangar, ou bâtiment clos sur tous ses côtés",
            "help_text": "Y compris serre agricole entièrement close, bâtiment sportif ou d’activité",
        },
    ),
    ("batiment_ouvert", "Toiture d’un bâtiment partiellement ouvert"),
    ("aucun", "Aucun panneau"),
)


class PhotovoltaiqueForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_30"

    activate = forms.BooleanField(
        label="Installation photovoltaïque",
        help_text="Rubrique 30 de l'évaluation environnementale",
        required=True,
        widget=forms.CheckboxInput,
    )
    puissance = DisplayChoiceField(
        label="Puissance totale des panneaux installés",
        help_text="Cumul autorisé depuis le 16 mai 2017",
        choices=PUISSANCE_CHOICES,
        widget=forms.RadioSelect,
        required=True,
    )
    localisation = DisplayChoiceField(
        label="Localisation des panneaux",
        choices=LOCALISATION_CHOICES,
        widget=forms.RadioSelect,
        required=True,
    )


class Photovoltaique(SelfDeclarationMixin, CriterionEvaluator):
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
        ("300_1000kWc", "aire_non_arti"): "cas_par_cas_ombriere",
        ("300_1000kWc", "batiment_clos"): "non_soumis_toiture",
        ("300_1000kWc", "batiment_ouvert"): "cas_par_cas_toiture",
        ("300_1000kWc", "aucun"): "non_soumis",
        ("gte_1000kWc", "sol"): "systematique_sol",
        ("gte_1000kWc", "aire_arti"): "non_soumis_ombriere",
        ("gte_1000kWc", "aire_non_arti"): "cas_par_cas_ombriere",
        ("gte_1000kWc", "batiment_clos"): "non_soumis_toiture",
        ("gte_1000kWc", "batiment_ouvert"): "systematique_toiture",
        ("gte_1000kWc", "aucun"): "non_soumis",
    }
    RESULT_MATRIX = {
        "non_soumis_ombriere": "non_soumis",
        "non_soumis_toiture": "non_soumis",
        "cas_par_cas_sol": "cas_par_cas",
        "cas_par_cas_toiture": "cas_par_cas",
        "cas_par_cas_ombriere": "cas_par_cas",
        "systematique_sol": "systematique",
        "systematique_toiture": "systematique",
    }

    def get_catalog_data(self, **kwargs):
        catalog = super().get_catalog_data(**kwargs)
        # We have to add a custom key to the template, because
        # django cannot access template values with a dash in the key
        if "evalenv_rubrique_30-puissance" in catalog:
            catalog["photovoltaic_power_over_1000kw"] = (
                catalog["evalenv_rubrique_30-puissance"] == "gte_1000kWc"
            )
        return catalog

    def get_result_data(self):
        form = self.get_form()
        form.is_valid()
        puissance = form.cleaned_data.get("puissance")
        localisation = form.cleaned_data.get("localisation")
        return puissance, localisation


TYPE_STATIONNEMENT_CHOICES = (
    (
        "public",
        {
            "label": "Ouvert au public",
            "help_text": """Dès lors que les emplacements sont accessibles à tous,
            y compris s’ils sont payants, ou fermés la nuit, ou réservés aux clients d’un commerce
            ou d’un établissement recevant du public""",
        },
        "Ouvert au public",
    ),
    (
        "mixed",
        "Mixte (au moins un emplacement ouvert au public)",
        "Mixte public-privé (au moins un emplacement est ouvert au public)",
    ),
    (
        "private",
        {
            "label": "Entièrement privé",
            "help_text": """Emplacements attachés à des logements ou réservés aux employés
            d’une entreprise ; en sous-sol ou en extérieur.""",
        },
        "Entièrement privé",
    ),
)

NB_EMPLACEMENTS_CHOICES = (
    ("0_49", "0 à 49"),
    ("gte_50", "50 ou plus"),
)


class AireDeStationnementForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_41"

    activate = forms.BooleanField(
        label="Aire de stationnement",
        help_text="Rubrique 41 de l'évaluation environnementale",
        required=True,
        widget=forms.CheckboxInput,
    )
    type_stationnement = DisplayChoiceField(
        label="Type de stationnement",
        help_text="""
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=extract_choices(TYPE_STATIONNEMENT_CHOICES),
        get_display_value=extract_display_function(TYPE_STATIONNEMENT_CHOICES),
    )
    nb_emplacements = DisplayChoiceField(
        label="Nombre total d'emplacements",
        help_text="""
            Somme des emplacements privés et publics.
            Cumul autorisé après le 16 mai 2017
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=NB_EMPLACEMENTS_CHOICES,
    )


class AireDeStationnement(SelfDeclarationMixin, CriterionEvaluator):
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
    ("0_6", "0 à 6"),
    ("7_199", "7 à 199"),
    ("gte_200", "200 ou plus"),
)


class CampingForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_42"

    activate = forms.BooleanField(
        label="Camping",
        help_text="Rubrique 42 de l'évaluation environnementale",
        required=True,
        widget=forms.CheckboxInput,
    )
    nb_emplacements = DisplayChoiceField(
        label="Nombre total d'emplacements",
        help_text="""
            De tentes, caravanes, résidences mobiles ou habitations légères de loisirs.
            Cumul autorisé après le 16 mai 2017.
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=NB_EMPLACEMENTS_CAMPING_CHOICES,
        display_label="Nombre total d'emplacements camping :",
    )


class Camping(SelfDeclarationMixin, CriterionEvaluator):
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
    (
        "autre",
        "Aucun de ces types",
    ),
)

CAPACITE_ACCUEIL_CHOICES = (
    ("lt_1000", "0 à 999 personnes"),
    ("gte_1000", "1 000 personnes ou plus"),
)


class EquipementSportifForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_44"

    activate = forms.BooleanField(
        label="Équipement de sport, de loisirs ou culturel",
        help_text="Rubrique 44 de l'évaluation environnementale",
        required=True,
        widget=forms.CheckboxInput,
    )
    type = DisplayChoiceField(
        label="Type d'équipement",
        required=True,
        widget=forms.RadioSelect,
        choices=TYPE_EQUIPEMENT_CHOICES,
        get_display_value=lambda value: (
            "Ni parc de loisirs, ni équipement sportif ou culturel"
            if value == "autre"
            else dict(TYPE_EQUIPEMENT_CHOICES).get(value, value)
        ),
    )
    capacite_accueil = forms.ChoiceField(
        label="Capacité d'accueil",
        required=True,
        widget=forms.RadioSelect,
        choices=CAPACITE_ACCUEIL_CHOICES,
    )


class EquipementSportif(SelfDeclarationMixin, CriterionEvaluator):
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


DEFRICHEMENT_DEBOISEMENT_CHOICE = (
    ("lt_05ha", "Moins de 0,5 ha"),
    ("gte_05ha", "0,5 ha ou plus"),
)

PREMIER_BOISEMENT_CHOICE = DEFRICHEMENT_DEBOISEMENT_CHOICE


class DefrichementBoisementForm(OptionalFormMixin, forms.Form):
    prefix = "evalenv_rubrique_47"

    activate = forms.BooleanField(
        label="Défrichement, déboisement ou boisement",
        help_text="""Rubrique 47 de l'évaluation environnementale<br>
            Cumul autorisé depuis le 16 mai 2017. Compter la superficie totale, même fragmentée.""",
        required=True,
        widget=forms.CheckboxInput,
    )
    defrichement_deboisement = DisplayChoiceField(
        label="Défrichement ou déboisement",
        help_text="""
            Toute opération volontaire (coupe rase, dessouchage…) ayant pour effet de détruire l’état boisé d’un terrain
            (qu’il soit à usage forestier ou non), et qui en change la destination : mise en culture, habitation, activité tertiaire…
            Voir <a href="https://www.ecologie.gouv.fr/sites/default/files/documents/%C3%89valuation%20environnementale%20des%20projets%20%E2%80%93%20Guide%20de%20lecture%20de%20la%20nomenclature.pdf" target="_blank" rel="noopener">
            guide de la nomenclature p. 58</a>.
        """,  # noqa
        required=True,
        widget=forms.RadioSelect,
        choices=DEFRICHEMENT_DEBOISEMENT_CHOICE,
    )
    premier_boisement = DisplayChoiceField(
        label="Premier boisement",
        help_text="""
            Ne concerne pas le reboisement de terrains qui étaient antérieurement à l'état boisé.
        """,
        required=True,
        widget=forms.RadioSelect,
        choices=PREMIER_BOISEMENT_CHOICE,
    )


class DefrichementDeboisement(SelfDeclarationMixin, CriterionEvaluator):
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


class PremierBoisement(SelfDeclarationMixin, CriterionEvaluator):
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


class OtherCriteria(SelfDeclarationMixin, CriterionEvaluator):
    choice_label = "Éval Env > Autres rubriques"
    slug = "autres_rubriques"

    CODES = ["non_disponible"]

    def evaluate(self):
        self._result_code, self._result = RESULTS.non_disponible, RESULTS.non_disponible

    def should_be_displayed(self):
        optional_criteria = self.moulinette.eval_env.get_optional_criteria()
        return not bool(optional_criteria)
