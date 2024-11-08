from django import forms

TYPES = (
    ("degradee", "Haie dégradée ou résiduelle basse"),
    ("buissonnante", "Haie buissonnante basse"),
    ("arbustive", "Haie arbustive basse"),
    ("alignement", "Alignement d'arbres"),
    ("mixte", "Mixte"),
)


class HedgeDataForm(forms.Form):
    hedge_type = forms.ChoiceField(choices=TYPES, label="Type de haie")
    sur_parcelle_pac = forms.BooleanField(label="Sur parcelle PAC", required=False)
    proximite_mare = forms.BooleanField(
        label="Présence d'une mare à moins de 200m", required=False
    )
