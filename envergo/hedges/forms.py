import copy
from abc import abstractmethod

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.module_loading import import_string
from django.utils.safestring import mark_safe

from envergo.hedges.models import (
    TO_PLANT,
    TO_REMOVE,
    HedgeData,
    HedgeTypeBase,
    HedgeTypeFactory,
)
from envergo.moulinette.forms.fields import (
    DisplayBooleanField,
    DisplayChoiceField,
    extract_choices,
    extract_display_function,
)
from envergo.utils.fields import HedgeChoiceField


class HedgePropertiesBaseForm(forms.Form):
    """Base Hedge properties form"""

    type_haie = forms.ChoiceField(
        choices=[],
        widget=HedgeChoiceField,
    )
    sur_parcelle_pac = forms.BooleanField(
        label="Sur une parcelle PAC",
        required=False,
    )
    bord_voie = forms.BooleanField(
        label="En bordure de route, voie ou chemin ouvert au public",
        required=False,
    )
    ripisylve = forms.BooleanField(
        label=mark_safe(
            "En bordure de cours d'eau ou de plan d'eau (haie ripisylve)"
            "<span class=\"fr-hint-text\">Y compris d'un canal ou d'une mare</span>"
        ),
        required=False,
    )
    proximite_mare = forms.BooleanField(
        label="Mare ou point d'eau à moins de 500 m",
        required=False,
    )
    bord_batiment = forms.BooleanField(
        label="En bordure de bâtiment",
        required=False,
    )
    parc_jardin = forms.BooleanField(
        label="Dans le parc ou jardin d'une habitation",
        required=False,
    )
    place_publique = forms.BooleanField(
        label="Sur une place publique",
        required=False,
    )

    def __init__(self, single_procedure, *args, **kwargs):
        super().__init__(*args, **kwargs)
        HedgeType = HedgeTypeFactory.build_from_context(
            single_procedure=single_procedure
        )
        self.fields["type_haie"].choices = HedgeType.choices
        self.fields["type_haie"].label = mark_safe(
            f"""
        <span>Type de haie</span>
        <a href="{HedgeType.faq_url}"
        target="_blank" rel="noopener">Aide</a>
        """
        )


MODE_DESTRUCTION_CHOICES = (
    ("arrachage", "Arrachage", "Arrachage"),
    (
        "coupe_a_blanc",
        mark_safe(
            f"""Coupe à blanc (sur essence ne recépant pas)
            <span class="fr-hint-text">
            <a href="{settings.HAIE_FAQ_URLS["TREE_SPECIES_COPPICING_CAPACITY"]}"
               target="_blank" rel="noopener">
            Liste des essences ne recépant pas</a></span>
            """
        ),
        "Coupe à blanc (sur essence ne recépant pas)",
    ),
    ("autre", "Autre", "Autre"),
)


class HedgeToRemovePropertiesRegimeUniqueForm(HedgePropertiesBaseForm):
    """Hedge to remove properties form"""

    mode_destruction = DisplayChoiceField(
        choices=extract_choices(MODE_DESTRUCTION_CHOICES),
        label="",
        widget=forms.RadioSelect,
        initial="arrachage",
        get_display_value=extract_display_function(MODE_DESTRUCTION_CHOICES),
    )
    vieil_arbre = forms.BooleanField(
        label=mark_safe(
            "Contient un ou plusieurs vieux arbres, fissurés ou avec cavités"
            '<span class="fr-hint-text">Arbres à partir de 20 cm de diamètre</span>'
        ),
        required=False,
    )

    fieldsets = {
        "Mode de destruction": ["mode_destruction"],
        "Caractéristiques naturelles": [
            "type_haie",
            "vieil_arbre",
            "ripisylve",
            "proximite_mare",
        ],
        "Situation": [
            "sur_parcelle_pac",
            "bord_voie",
            "bord_batiment",
            "parc_jardin",
            "place_publique",
        ],
    }

    @classmethod
    @abstractmethod
    def human_readable_name(cls):
        return "Régime unique"


class HedgeToPlantPropertiesRegimeUniqueForm(HedgePropertiesBaseForm):
    """Hedge to plant properties form"""

    sous_ligne_electrique = forms.BooleanField(
        label="Sous une ligne électrique ou téléphonique",
        required=False,
    )

    fieldsets = {
        "Caractéristiques naturelles": [
            "type_haie",
            "ripisylve",
            "proximite_mare",
        ],
        "Situation": [
            "sur_parcelle_pac",
            "bord_voie",
            "sous_ligne_electrique",
            "bord_batiment",
            "parc_jardin",
            "place_publique",
        ],
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove the 'degradee' option from type_haie choices
        self.fields["type_haie"].choices = [
            choice
            for choice in self.fields["type_haie"].choices
            if choice[0] != HedgeTypeBase.DEGRADEE
        ]

    @classmethod
    @abstractmethod
    def human_readable_name(cls):
        return "Régime unique"


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
    interchamp = DisplayBooleanField(
        label=mark_safe(
            'Haie inter-champ <span class="fr-hint-text">Y compris en bord de chemin entre deux parcelles</span>'
        ),
        required=False,
        display_label="Haie inter-champ",
    )


class HedgeToRemovePropertiesCalvadosForm(
    EssencesNonBocageresMixin,
    SurTalusMixin,
    InterchampMixin,
    HedgeToRemovePropertiesRegimeUniqueForm,
):
    """Hedge to remove properties form : Calvados specific"""

    recemment_plantee = DisplayBooleanField(
        label=mark_safe(
            'Haie récemment plantée <span class="fr-hint-text">Après le 1er janvier 2023</span>'
        ),
        required=False,
        display_label="Haie récemment plantée",
    )

    fieldsets = copy.deepcopy(HedgeToRemovePropertiesRegimeUniqueForm.fieldsets)

    fieldsets["Caractéristiques naturelles"].insert(1, "recemment_plantee")
    fieldsets["Caractéristiques naturelles"].insert(3, "essences_non_bocageres")
    fieldsets["Caractéristiques naturelles"].insert(4, "sur_talus")
    fieldsets["Situation"].insert(1, "interchamp")

    @classmethod
    def human_readable_name(cls):
        return "Calvados avant r.u. (interchamp, talus, essences non bocagères, type de plantation)"


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
    HedgeToPlantPropertiesRegimeUniqueForm,
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
        **copy.deepcopy(HedgeToPlantPropertiesRegimeUniqueForm.fieldsets),
    }
    fieldsets["Caractéristiques naturelles"].insert(1, "essences_non_bocageres")
    fieldsets["Caractéristiques naturelles"].insert(1, "sur_talus")
    fieldsets["Situation"].insert(1, "interchamp")

    @classmethod
    def human_readable_name(cls):
        return "Calvados avant r.u. (interchamp, talus, essences non bocagères, type de plantation)"


class ConnexionBoisementMixin(forms.Form):
    connexion_boisement = forms.BooleanField(
        label="Connectée à un boisement ou à une autre haie",
        required=False,
    )


class HedgeToRemovePropertiesAisneForm(
    ConnexionBoisementMixin, HedgeToRemovePropertiesRegimeUniqueForm
):
    """Hedge to remove properties form : Aisne specific"""

    fieldsets = copy.deepcopy(HedgeToRemovePropertiesRegimeUniqueForm.fieldsets)
    fieldsets["Situation"].append("connexion_boisement")

    @classmethod
    def human_readable_name(cls):
        return "Aisne avant r.u. (connexion boisement)"


class HedgeToPlantPropertiesAisneForm(
    ConnexionBoisementMixin, HedgeToPlantPropertiesRegimeUniqueForm
):
    """Hedge to plant properties form : Aisne specific"""

    fieldsets = copy.deepcopy(HedgeToPlantPropertiesRegimeUniqueForm.fieldsets)
    fieldsets["Situation"].append("connexion_boisement")

    @classmethod
    def human_readable_name(cls):
        return "Aisne avant r.u. (connexion boisement)"


class LatLngForm(forms.Form):
    """A single geographic coordinate of a hedge geometry."""

    lat = forms.FloatField()
    lng = forms.FloatField()


class HedgeEntryForm(forms.Form):
    """Validate a single hedge entry submitted by the hedge input ui.

    The nested structures delegate to sub-forms: each latLngs point to
    LatLngForm, and additionalData to the department's hedge properties
    form, so only known property fields are kept.
    """

    id = forms.CharField()
    type = forms.ChoiceField(choices=[(TO_REMOVE, TO_REMOVE), (TO_PLANT, TO_PLANT)])
    latLngs = forms.JSONField()
    additionalData = forms.JSONField(required=False)

    def __init__(self, *args, config=None, **kwargs):
        self.config = config
        super().__init__(*args, **kwargs)

    def clean_latLngs(self):
        latLngs = self.cleaned_data["latLngs"]
        if not isinstance(latLngs, list) or len(latLngs) < 2:
            raise ValidationError("Une haie requiert au moins deux points")

        points = []
        for point in latLngs:
            point_form = LatLngForm(data=point if isinstance(point, dict) else {})
            if not point_form.is_valid():
                raise ValidationError(
                    "Chaque point doit avoir des coordonnées lat et lng numériques"
                )
            points.append(point_form.cleaned_data)
        return points

    def clean_additionalData(self):
        additional_data = self.cleaned_data["additionalData"]
        if additional_data is not None and not isinstance(additional_data, dict):
            raise ValidationError("additionalData doit être un objet")
        return additional_data or {}

    def clean(self):
        cleaned_data = super().clean()
        hedge_type = cleaned_data.get("type")
        if hedge_type and "additionalData" in cleaned_data:
            properties_form = self.get_properties_form(hedge_type)
            if not properties_form.is_valid():
                raise ValidationError(
                    f"Caractéristiques de haie invalides : {properties_form.errors.as_text()}"
                )
            cleaned_data["additionalData"] = properties_form.cleaned_data
        return cleaned_data

    def get_properties_form(self, hedge_type):
        """Build the properties form matching the department config."""
        config = self.config
        if config:
            form_path = (
                config.hedge_to_remove_properties_form
                if hedge_type == TO_REMOVE
                else config.hedge_to_plant_properties_form
            )
            form_class = import_string(form_path)
            single_procedure = config.single_procedure
        else:
            form_class = (
                HedgeToRemovePropertiesRegimeUniqueForm
                if hedge_type == TO_REMOVE
                else HedgeToPlantPropertiesRegimeUniqueForm
            )
            single_procedure = True

        return form_class(
            single_procedure=single_procedure,
            data=self.cleaned_data["additionalData"],
        )


class HedgeForm(forms.Form):
    """Hedge form to get HedgeData object"""

    haies = forms.UUIDField(label="Haies", required=False)

    def clean_haies(self):
        """Get HedgeData object or raise ValidationError"""
        data = self.cleaned_data["haies"]
        if not data:
            return data
        try:
            hedge_data_object = HedgeData.objects.get(pk=data)
            data = hedge_data_object
        except HedgeData.DoesNotExist:
            raise ValidationError("Données de haies inexistantes")

        return data
