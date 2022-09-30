from django import forms
from django.utils.translation import gettext_lazy as _

MSG_PLACEHOLDER = "Un élément qui manque de clarté, une information erronée, une proposition d'amélioration…"


class FeedbackForm(forms.Form):
    message = forms.CharField(
        required=True,
        label="Que souhaitez-vous nous demander ou signaler ?",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": MSG_PLACEHOLDER}),
    )
    contact = forms.CharField(
        required=False,
        label="Email ou téléphone",
        help_text="Pour vous recontacter si vous souhaitez une réponse",
    )
