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
    sur_parcelle_pac = forms.BooleanField(
        label="Située sur une parcelle PAC",
        required=False,
    )
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
            choice for choice in TYPES if choice[0] != "degradee"
        ]
