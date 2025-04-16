import copy

from django import forms
from django.utils.safestring import mark_safe

from envergo.hedges.models import HEDGE_TYPES


class HedgePropertiesBaseForm(forms.Form):
    type_haie = forms.ChoiceField(
        choices=HEDGE_TYPES,
        label=mark_safe(
            """
        <span>Type de haie</span>
        <a href="https://docs.google.com/document/d/1MAzLdH2ZsHHoHnK9ZgF47PrFT9SfnLnMA_IZwUI3sUc/edit?usp=sharing)"
        target="_blank" rel="noopener">Aide</a>
        """
        ),
    )
    sur_parcelle_pac = forms.BooleanField(
        label="Située sur une parcelle PAC",
        required=False,
    )
    position = forms.ChoiceField(
        choices=[
            ("interchamp", "Inter-champ"),
            ("bord_route", "Bordure de voirie ouverte à la circulation"),
            ("autre", "Autre (bord de chemin, bâtiment…)"),
        ],
        label="Situation de la haie",
    )
    proximite_mare = forms.BooleanField(
        label="Mare à moins de 200 m",
        required=False,
    )


class HedgeToRemovePropertiesForm(HedgePropertiesBaseForm):
    mode_destruction = forms.ChoiceField(
        choices=[
            ("arrachage", "Arrachage"),
            ("coupe_a_blanc", "Coupe à blanc (sur essence ne recépant pas)"),
            ("autre", "Autre"),
        ],
        label="",
    )
    vieil_arbre = forms.BooleanField(
        label="Contient un ou plusieurs vieux arbres, fissurés ou avec cavités",
        required=False,
    )

    fieldsets = {
        "Mode de destruction": ["mode_destruction"],
        "Caractéristiques de la haie": ["type_haie", "vieil_arbre"],
        "Situation de la haie": ["sur_parcelle_pac", "position", "proximite_mare"],
    }


class HedgeToPlantPropertiesForm(HedgePropertiesBaseForm):

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
            "position",
            "proximite_mare",
            "sous_ligne_electrique",
        ],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the 'degradee' option from type_haie choices
        self.fields["type_haie"].choices = [
            choice for choice in HEDGE_TYPES if choice[0] != "degradee"
        ]


class EssencesNonBocageresMixin(forms.Form):
    essences_non_bocageres = forms.BooleanField(
        label="Composée d'essences non bocagères Thuya, cyprès, laurier-palme, photinia, eleagnus…",
        required=False,
    )


class SurTalusMixin(forms.Form):
    sur_talus = forms.BooleanField(
        label="Haie sur talus",
        required=False,
    )


class HedgeToRemovePropertiesCalvadosForm(
    EssencesNonBocageresMixin, SurTalusMixin, HedgeToRemovePropertiesForm
):
    recemment_plantee = forms.BooleanField(
        label="Haie récemment plantée Après le 1er janvier 2023",
        required=False,
    )

    fieldsets = copy.deepcopy(HedgeToRemovePropertiesForm.fieldsets)
    fieldsets["Caractéristiques de la haie"].extend(
        ["essences_non_bocageres", "recemment_plantee"]
    )
    fieldsets["Situation de la haie"].extend(["sur_talus"])


class HedgeToPlantPropertiesCalvadosForm(
    EssencesNonBocageresMixin, SurTalusMixin, HedgeToPlantPropertiesForm
):
    mode_plantation = forms.ChoiceField(
        choices=[
            ("plantation", "Plantation nouvelle ou remplacement d'une haie existante"),
            (
                "renforcement",
                "Renforcement d'une haie existante par exemple en garnissant la strate arbustive d’un alignement "
                "d’arbres, ou en plantant des arbres de haut-jet dans une haie d’arbustes",
            ),
            (
                "reconnexion",
                "Reconnexion d'une haie discontinue c'est-à-dire en « bouchant les trous »",
            ),
        ],
        label="",
    )

    fieldsets = {
        "Type de plantation": ["mode_plantation"],
        **copy.deepcopy(HedgeToPlantPropertiesForm.fieldsets),
    }
    fieldsets["Caractéristiques de la haie"].extend(["essences_non_bocageres"])
    fieldsets["Situation de la haie"].extend(["sur_talus"])


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

    fieldsets = copy.deepcopy(HedgeToRemovePropertiesForm.fieldsets)
    fieldsets["Situation de la haie"].extend(
        ["proximite_point_eau", "connexion_boisement"]
    )


class HedgeToPlantPropertiesAisneForm(
    ProximitePointEauMixin, ConnexionBoisementMixin, HedgeToPlantPropertiesForm
):

    fieldsets = copy.deepcopy(HedgeToPlantPropertiesForm.fieldsets)
    fieldsets["Situation de la haie"].extend(
        ["proximite_point_eau", "connexion_boisement"]
    )
