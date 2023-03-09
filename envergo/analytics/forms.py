from django import forms
from django.utils.safestring import mark_safe

MSG_PLACEHOLDER = "Un élément qui manque de clarté, une information erronée, une proposition d'amélioration…"

YOU_ARE_CHOICES = (
    ("porteur", "Porteur de projet"),
    ("bureau", "Bureau d'études / géomètre"),
    ("architecte", "Architecte"),
    ("mairie", "Mairie"),
    ("instructeur", "Service instructeur"),
    ("autre", "Autre"),
)

# The "Oui" and "Non" values are hardcoded in the feedback_form.js file.
# Do no change, or change both files.
FEEDBACK_CHOICES = (
    (
        "Oui",
        mark_safe('<span class="fr-icon-thumb-up-fill" aria-hidden="true"></span> Oui'),
    ),
    (
        "Non",
        mark_safe(
            '<span class="fr-icon-thumb-down-fill" aria-hidden="true"></span> Non'
        ),
    ),
)


class FeedbackRespondForm(forms.Form):
    """Simple form to process the ajax request to log the feedback.

    This is only used in a POST request, this form is never displayed.
    """

    feedback = forms.ChoiceField(
        required=True,
        label="Cette évaluation vous est-elle utile ?",
        choices=FEEDBACK_CHOICES,
    )
    moulinette_data = forms.JSONField(required=False, widget=forms.HiddenInput)


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
        required=True,
        label="Vous êtes…",
        choices=YOU_ARE_CHOICES,
        widget=forms.RadioSelect,
    )
    contact = forms.CharField(
        required=False,
        label="Email ou téléphone",
        help_text="Pour vous recontacter si vous souhaitez une réponse",
    )
    moulinette_data = forms.JSONField(required=False, widget=forms.HiddenInput)

    def get_you_are_display(self):
        """Get display value for `you_are` field."""

        choices = dict(YOU_ARE_CHOICES)
        val = self.cleaned_data["you_are"]
        return choices[val]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["you_are"].widget.fieldset_class = "fr-fieldset--inline"


class FeedbackFormUseful(FeedbackForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].label = "En quoi cette évaluation vous est-elle utile ?"
        self.fields["message"].widget.attrs[
            "placeholder"
        ] = "Une information nouvelle ? Une procédure clarifiée ? Une décision facilitée ?"


class FeedbackFormUseless(FeedbackForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].label = "Que pouvons-nous améliorer ?"
        self.fields["message"].widget.attrs[
            "placeholder"
        ] = "Un élément qui manque de clarté, une information erronée, une proposition d'amélioration…"


class EventForm(forms.Form):
    category = forms.CharField(max_length=64)
    action = forms.CharField(max_length=64)
    metadata = forms.JSONField(required=False)
