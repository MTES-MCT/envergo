from collections import OrderedDict

from django import forms
from django.utils.safestring import mark_safe

from envergo.hedges.models import HEDGE_TYPES


class HedgeDataBaseForm(forms.Form):
    hedge_type = forms.ChoiceField(
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
    proximite_mare = forms.BooleanField(
        label="Mare à moins de 200 m",
        required=False,
    )
    proximite_point_eau = forms.BooleanField(
        label="Mare ou ruisseau à moins de 10 m",
        required=False,
    )
    connexion_boisement = forms.BooleanField(
        label="Connectée à un boisement ou à une autre haie",
        required=False,
    )


class HedgeToRemoveDataForm(HedgeDataBaseForm):
    vieil_arbre = forms.BooleanField(
        label="Contient un ou plusieurs vieux arbres, fissurés ou avec cavités",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Reorder the fields
        self.fields = OrderedDict(
            [
                ("hedge_type", self.fields["hedge_type"]),
                ("sur_parcelle_pac", self.fields["sur_parcelle_pac"]),
                ("vieil_arbre", self.fields["vieil_arbre"]),
                ("proximite_mare", self.fields["proximite_mare"]),
                ("proximite_point_eau", self.fields["proximite_point_eau"]),
                ("connexion_boisement", self.fields["connexion_boisement"]),
            ]
        )


class HedgeToPlantDataForm(HedgeDataBaseForm):

    sous_ligne_electrique = forms.BooleanField(
        label="Située sous une ligne électrique",
        required=False,
    )
    proximite_voirie = forms.BooleanField(
        label="Située en bordure de voirie", required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the 'degradee' option from hedge_type choices
        self.fields["hedge_type"].choices = [
            choice for choice in HEDGE_TYPES if choice[0] != "degradee"
        ]


class RemovalModeForm(forms.Form):
    mode_destruction = forms.ChoiceField(
        choices=[
            ("arrachage", "Arrachage"),
            ("coupe_a_blanc", "Coupe à blanc (sur essence ne recépant pas)"),
            ("autre", "Autre"),
        ],
        label="",
    )


class PlantationTypeForm(forms.Form):
    pass


class PlantationModeMixin:
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


class PlantationTypeCalvadosForm(PlantationModeMixin, PlantationTypeForm):
    pass


class HedgePropertiesForm(forms.Form):
    hedge_type = forms.ChoiceField(
        choices=HEDGE_TYPES,
        label=mark_safe(
            """
        <span>Type de haie</span>
        <a href="https://docs.google.com/document/d/1MAzLdH2ZsHHoHnK9ZgF47PrFT9SfnLnMA_IZwUI3sUc/edit?usp=sharing)"
        target="_blank" rel="noopener">Aide</a>
        """
        ),
    )


class HedgePropertiesRemovalForm(HedgePropertiesForm):
    vieil_arbre = forms.BooleanField(
        label="Contient un ou plusieurs vieux arbres, fissurés ou avec cavités",
        required=False,
    )


class EssencesNonBocageresMixin:
    essences_non_bocageres = forms.BooleanField(
        label="Composée d'essences non bocagères Thuya, cyprès, laurier-palme, photinia, eleagnus…",
        required=False,
    )


class HedgePropertiesRemovalCalvadosForm(
    EssencesNonBocageresMixin, HedgePropertiesRemovalForm
):
    recemment_plantee = forms.BooleanField(
        label="Haie récemment plantée Après le 1er janvier 2023",
        required=False,
    )


class HedgePropertiesPlantationCalvadosForm(
    EssencesNonBocageresMixin, HedgePropertiesForm
):
    recemment_plantee = forms.BooleanField(
        label="Haie récemment plantée Après le 1er janvier 2023",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the 'degradee' option from hedge_type choices
        self.fields["hedge_type"].choices = [
            choice for choice in HEDGE_TYPES if choice[0] != "degradee"
        ]


class HedgeLocationForm(forms.Form):
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


class HedgeLocationPlantationForm(HedgeLocationForm):
    sous_ligne_electrique = forms.BooleanField(
        label="Sous une ligne électrique ou téléphonique",
        required=False,
    )


class SurTalusMixin:
    sur_talus = forms.BooleanField(
        label="Haie sur talus",
        required=False,
    )


class HedgeLocationRemovalCalvadosForm(SurTalusMixin, HedgeLocationForm):
    pass


class HedgeLocationPlantationCalvadosForm(SurTalusMixin, HedgeLocationPlantationForm):
    pass


class ProximitePointEauMixin:
    proximite_point_eau = forms.BooleanField(
        label="Mare ou ruisseau à moins de 10 m",
        required=False,
    )


class ConnexionBoisementMixin:
    connexion_boisement = forms.BooleanField(
        label="Connectée à un boisement ou à une autre haie",
        required=False,
    )


class HedgeLocationRemovalAisneForm(
    ProximitePointEauMixin, ConnexionBoisementMixin, HedgeLocationForm
):
    pass


class HedgeLocationPlantationAisneForm(
    ProximitePointEauMixin, ConnexionBoisementMixin, HedgeLocationPlantationForm
):
    pass
