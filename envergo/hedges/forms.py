import copy
from abc import abstractmethod

from django import forms
from django.utils.safestring import mark_safe

from envergo.hedges.models import HEDGE_TYPES
from envergo.moulinette.forms.fields import DisplayBooleanField
from envergo.utils.fields import AllowDisabledSelect


class HedgePropertiesBaseForm(forms.Form):
    """Base Hedge properties form"""

    type_haie = forms.ChoiceField(
        choices=(("", "Sélectionner une option"),) + HEDGE_TYPES,
        label=mark_safe(
            """
        <span>Type de haie</span>
        <a href="https://docs.google.com/document/d/1MAzLdH2ZsHHoHnK9ZgF47PrFT9SfnLnMA_IZwUI3sUc/edit?usp=sharing)"
        target="_blank" rel="noopener">Aide</a>
        """
        ),
        widget=AllowDisabledSelect(),
    )
    sur_parcelle_pac = forms.BooleanField(
        label="Située sur une parcelle PAC",
        required=False,
    )
    proximite_mare = forms.BooleanField(
        label="Mare à moins de 200 m",
        required=False,
    )


MODE_DESTRUCTION_CHOICES = (
    ("arrachage", "Arrachage"),
    ("coupe_a_blanc", "Coupe à blanc (sur essence ne recépant pas)"),
    ("autre", "Autre"),
)


class HedgeToRemovePropertiesForm(HedgePropertiesBaseForm):
    """Hedge to remove properties form"""

    mode_destruction = forms.ChoiceField(
        choices=MODE_DESTRUCTION_CHOICES,
        label="",
        widget=forms.RadioSelect,
        initial="arrachage",
    )
    vieil_arbre = forms.BooleanField(
        label="Contient un ou plusieurs vieux arbres, fissurés ou avec cavités",
        required=False,
    )

    bord_voie = forms.BooleanField(
        label="Bord de route, voie ou chemin ouvert au public",
        required=False,
    )

    fieldsets = {
        "Mode de destruction": ["mode_destruction"],
        "Caractéristiques de la haie": ["type_haie", "vieil_arbre"],
        "Situation de la haie": ["sur_parcelle_pac", "bord_voie", "proximite_mare"],
    }

    @classmethod
    @abstractmethod
    def human_readable_name(cls):
        return "Caractéristiques de base"


class HedgeToPlantPropertiesForm(HedgePropertiesBaseForm):
    """Hedge to plant properties form"""

    sous_ligne_electrique = forms.BooleanField(
        label="Sous une ligne électrique ou téléphonique",
        required=False,
    )

    fieldsets = {
        "Caractéristiques de la haie": [
            "type_haie",
        ],
        "Situation de la haie": [
            "sur_parcelle_pac",
            "proximite_mare",
            "sous_ligne_electrique",
        ],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the 'degradee' option from type_haie choices
        self.fields["type_haie"].choices = [
            choice
            for choice in self.fields["type_haie"].choices
            if choice[0] != "degradee"
        ]

    @classmethod
    @abstractmethod
    def human_readable_name(cls):
        return "Caractéristiques de base"


class EssencesNonBocageresMixin(forms.Form):
    essences_non_bocageres = DisplayBooleanField(
        label=mark_safe(
            "Composée d'essences non bocagères "
            '<span class="fr-hint-text">Thuya, cyprès, laurier-palme, photinia, eleagnus…</span>'
        ),
        required=False,
        display_label="Composée d'essences non bocagères",
    )


class SurTalusMixin(forms.Form):
    sur_talus = forms.BooleanField(
        label="Haie sur talus",
        required=False,
    )


class InterchampMixin(forms.Form):
    interchamp = forms.BooleanField(
        label="Haie inter-champ",
        required=False,
    )


class HedgeToRemovePropertiesCalvadosForm(
    EssencesNonBocageresMixin,
    SurTalusMixin,
    InterchampMixin,
    HedgeToRemovePropertiesForm,
):
    """Hedge to remove properties form : Calvados specific"""

    recemment_plantee = DisplayBooleanField(
        label=mark_safe(
            'Haie récemment plantée <span class="fr-hint-text">Après le 1er janvier 2023</span>'
        ),
        required=False,
        display_label="Haie récemment plantée",
    )

    fieldsets = copy.deepcopy(HedgeToRemovePropertiesForm.fieldsets)

    fieldsets["Caractéristiques de la haie"].append("essences_non_bocageres")
    fieldsets["Caractéristiques de la haie"].insert(1, "recemment_plantee")
    fieldsets["Situation de la haie"].insert(1, "interchamp")
    fieldsets["Situation de la haie"].insert(2, "sur_talus")

    @classmethod
    def human_readable_name(cls):
        return "Caractéristiques du Calvados ( + talus, essences non bocagères, récemment plantée)"


MODE_PLANTATION_CHOICES = (
    (
        "plantation",
        mark_safe(
            'Plantation nouvelle <span class="fr-hint-text">ou remplacement d\'une haie à détruire</span>'
        ),
        "Plantation nouvelle ou remplacement",
    ),
    (
        "renforcement",
        mark_safe(
            "Renforcement d'une haie existante "
            '<span class="fr-hint-text">par exemple en garnissant la strate arbustive d’un alignement d’arbres,'
            " ou en plantant des arbres de haut-jet dans une haie d’arbustes</span>"
        ),
        "Renforcement d'une haie existante",
    ),
    (
        "reconnexion",
        mark_safe(
            "Reconnexion d'une haie discontinue "
            '<span class="fr-hint-text">c\'est-à-dire en « bouchant les trous »</span>'
        ),
        "Reconnexion d'une haie discontinue",
    ),
)


class HedgeToPlantPropertiesCalvadosForm(
    EssencesNonBocageresMixin,
    SurTalusMixin,
    InterchampMixin,
    HedgeToPlantPropertiesForm,
):
    """Hedge to plant properties form : Calvados specific"""

    mode_plantation = forms.ChoiceField(
        choices=[(first, second) for first, second, _ in MODE_PLANTATION_CHOICES],
        label="",
        widget=forms.RadioSelect,
        initial="plantation",
    )

    fieldsets = {
        "Type de plantation": ["mode_plantation"],
        **copy.deepcopy(HedgeToPlantPropertiesForm.fieldsets),
    }
    fieldsets["Caractéristiques de la haie"].append("essences_non_bocageres")
    fieldsets["Situation de la haie"].insert(1, "interchamp")
    fieldsets["Situation de la haie"].insert(2, "sur_talus")

    @classmethod
    def human_readable_name(cls):
        return "Caractéristiques du Calvados ( + interchamp, talus, essences non bocagères, type de plantation)"


class ProximitePointEauMixin(forms.Form):
    proximite_point_eau = forms.BooleanField(
        label="Mare ou ruisseau à moins de 10 m",
        required=False,
    )


class ConnexionBoisementMixin(forms.Form):
    connexion_boisement = forms.BooleanField(
        label="Connectée à un boisement ou à une autre haie",
        required=False,
    )


class HedgeToRemovePropertiesAisneForm(
    ProximitePointEauMixin, ConnexionBoisementMixin, HedgeToRemovePropertiesForm
):
    """Hedge to remove properties form : Aisne specific"""

    fieldsets = copy.deepcopy(HedgeToRemovePropertiesForm.fieldsets)
    fieldsets["Situation de la haie"].append("connexion_boisement")
    fieldsets["Situation de la haie"].insert(3, "proximite_point_eau")

    @classmethod
    def human_readable_name(cls):
        return "Caractéristiques de l'Aisne ( + proximité point d'eau, connexion boisement)"


class HedgeToPlantPropertiesAisneForm(
    ProximitePointEauMixin, ConnexionBoisementMixin, HedgeToPlantPropertiesForm
):
    """Hedge to plant properties form : Aisne specific"""

    fieldsets = copy.deepcopy(HedgeToPlantPropertiesForm.fieldsets)
    fieldsets["Situation de la haie"].append("connexion_boisement")
    fieldsets["Situation de la haie"].insert(2, "proximite_point_eau")

    @classmethod
    def human_readable_name(cls):
        return "Caractéristiques de l'Aisne ( + proximité point d'eau, connexion boisement)"
