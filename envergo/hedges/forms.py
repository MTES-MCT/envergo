from django import forms
from django.utils.safestring import mark_safe

TYPES = (
    ("degradee", "Haie dégradée ou résiduelle basse"),
    ("buissonnante", "Haie buissonnante basse"),
    ("arbustive", "Haie arbustive basse"),
    ("mixte", "Haie mixte"),
    ("alignement", "Alignement d'arbres"),
)


class HedgeDataForm(forms.Form):
    hedge_type = forms.ChoiceField(
        choices=TYPES,
        label=mark_safe(
            """
        <span>Type de haie</span>
        <a href="https://docs.google.com/document/d/1MAzLdH2ZsHHoHnK9ZgF47PrFT9SfnLnMA_IZwUI3sUc/edit?usp=sharing)"
        target="_blank" rel="noopener">Aide</a>
        """
        ),
    )
    sur_parcelle_pac = forms.BooleanField(
        label="Située sur une parcelle PAC", required=False
    )
    proximite_mare = forms.BooleanField(
        label="Présence d'une mare à moins de 200 m", required=False
    )
