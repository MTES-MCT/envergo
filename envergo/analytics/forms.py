from django import forms

MSG_PLACEHOLDER = "Un élément qui manque de clarté, une information erronée, une proposition d'amélioration…"

YOU_ARE_CHOICES = (
    ('porteur', 'Porteur de projet'),
    ('architecte', 'Architecte'),
    ('bureau', 'Bureau d\'étude / géomètre'),
    ('mairie', 'Mairie'),
    ('instructeur', 'Service instructeur'),
    ('autre', 'Autre'),
)


class FeedbackForm(forms.Form):
    message = forms.CharField(
        required=True,
        label="Que souhaitez-vous nous demander ou signaler ?",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": MSG_PLACEHOLDER}))
    you_are = forms.ChoiceField(
        required=True,
        label="Vous êtes",
        choices=YOU_ARE_CHOICES)
    contact = forms.CharField(
        required=False,
        label="Email ou téléphone",
        help_text="Pour vous recontacter si vous souhaitez une réponse")
