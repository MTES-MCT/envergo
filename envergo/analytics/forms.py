from django import forms
from django.utils.safestring import mark_safe

MSG_PLACEHOLDER = "Un élément qui manque de clarté, une information erronée, une proposition d'amélioration…"

YOU_ARE_CHOICES = (
    ("porteur", "Porteur de projet"),
    ("architecte", "Architecte"),
    ("bureau", "Bureau d'étude / géomètre"),
    ("mairie", "Mairie"),
    ("instructeur", "Service instructeur"),
    ("autre", "Autre"),
)

FEEDBACK_CHOICES = (
    (
        "oui",
        mark_safe('<span class="fr-icon-thumb-up-fill" aria-hidden="true"></span> Oui'),
    ),
    (
        "non",
        mark_safe(
            '<span class="fr-icon-thumb-down-fill" aria-hidden="true"></span> Non'
        ),
    ),
)


class FeedbackForm(forms.Form):
    feedback = forms.ChoiceField(
        required=True,
        label="Cette évaluation vous est-elle utile ?",
        choices=FEEDBACK_CHOICES,
        widget=forms.HiddenInput,
    )
    message = forms.CharField(
        required=True,
        label="Que souhaitez-vous nous demander ou signaler ?",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": MSG_PLACEHOLDER}),
    )
    you_are = forms.ChoiceField(
        required=True, label="Vous êtes", choices=YOU_ARE_CHOICES
    )
    contact = forms.CharField(
        required=False,
        label="Email ou téléphone",
        help_text="Pour vous recontacter si vous souhaitez une réponse",
    )
