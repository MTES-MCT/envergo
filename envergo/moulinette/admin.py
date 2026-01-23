from django import forms
from django.contrib import admin
from django.template.defaultfilters import truncatechars
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.geodata.admin import DepartmentsListFilter
from envergo.moulinette.models import (
    REGULATIONS,
    ActionToTake,
    ConfigAmenagement,
    ConfigHaie,
    Criterion,
    MoulinetteTemplate,
    Perimeter,
    Regulation,
)
from envergo.moulinette.regulations import CriterionEvaluator, RegulationEvaluator
from envergo.moulinette.utils import get_template_choices, list_moulinette_templates
from envergo.utils.widgets import JSONWidget


class MapDepartmentsListFilter(DepartmentsListFilter):
    title = _("Departments")
    parameter_name = "departments"
    template = "admin/choice_filter.html"

    def queryset(self, request, queryset):
        lookup_value = self.value()
        if lookup_value:
            queryset = queryset.filter(
                activation_map__departments__contains=[lookup_value]
            )
        return queryset


class RegulationAdminForm(forms.ModelForm):

    def get_initial_for_field(self, field, field_name):
        """Prevent Evaluator choice to be instanciated.

        In the legacy's version of this function, callable values are, well,
        called.

        But since we have a custom field that should return
        `RegulationEvaluator` subclasses, we don't want the form to actually
        instanciate those classes.
        """

        value = self.initial.get(field_name, field.initial)
        if callable(value) and not issubclass(value, RegulationEvaluator):
            value = value()
        return value

    def clean(self):
        data = super().clean()
        show_map = bool(data.get("show_map"))
        has_map_factory_name = bool(data.get("map_factory_name"))
        if show_map and not has_map_factory_name:
            raise forms.ValidationError(
                {
                    "map_factory_name": "Ce champ est obligatoire lorsque l'on veut afficher la carte du périmètre."
                }
            )
        return data


@admin.register(Regulation)
class RegulationAdmin(admin.ModelAdmin):
    list_display = [
        "get_regulation_display",
        "regulation_slug",
        "show_map",
        "weight",
        "display_order",
    ]
    list_editable = ["weight", "display_order"]
    form = RegulationAdminForm

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by("weight")

    @admin.display(description=_("Regulation slug"))
    def regulation_slug(self, obj):
        return obj.regulation


class CriterionAdminForm(forms.ModelForm):
    header = forms.CharField(
        label=_("Header"),
        required=False,
        widget=admin.widgets.AdminTextareaWidget(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "perimeter" in self.fields:
            perimeter_field = self.fields["perimeter"]
            perimeter_field.label_from_instance = (
                lambda perimeter: perimeter.backend_name
            )

        if "activation_map" in self.fields:
            self.fields["activation_map"].queryset = self.fields[
                "activation_map"
            ].queryset.defer("geometry")

    def get_initial_for_field(self, field, field_name):
        """Prevent Evaluator choice to be instanciated.

        In the legacy's version of this function, callable values are, well,
        called.

        But since we have a custom field that should return
        `CriterionEvaluator` subclasses, we don't want the form to actually
        instanciate those classes.
        """

        value = self.initial.get(field_name, field.initial)
        if callable(value) and not issubclass(value, CriterionEvaluator):
            value = value()
        return value

    def clean_evaluator_settings(self):
        """Ensure an empty value can be converted to an empty json dict."""
        value = self.cleaned_data["evaluator_settings"]
        value = {} if value is None else value
        return value

    def clean(self):
        """Ensure required action and stake are both set if one is set."""

        data = super().clean()
        has_required_action = bool(data.get("required_action"))
        has_stake = bool(data.get("required_action_stake"))
        if any([has_required_action, has_stake]) and not all(
            [has_required_action, has_stake]
        ):
            raise forms.ValidationError(
                "Both required action and stake are required if one is set."
            )
        return data


class MoulinetteTemplateInline(admin.StackedInline):
    model = MoulinetteTemplate
    extra = 0
    fields = ["key", "content"]


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = [
        "backend_title",
        "is_optional",
        "regulation",
        "perimeter_list",
        "activation_map_column",
        "activation_distance_column",
        "evaluator_column",
        "weight",
    ]
    readonly_fields = ["unique_slug"]
    autocomplete_fields = ["activation_map", "perimeter"]
    form = CriterionAdminForm
    search_fields = [
        "backend_title",
        "title",
        "regulation__regulation",
        "activation_map__name",
    ]
    list_editable = ["weight"]
    list_filter = ["regulation", "is_optional", MapDepartmentsListFilter, "evaluator"]
    sortable_by = ["backend_title", "activation_map", "activation_distance"]
    inlines = [MoulinetteTemplateInline]

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not request.user.has_perm("moulinette.change_criterion"):
            # Replace 'evaluator' with 'evaluator_column' for users without edit rights
            for fieldset in fieldsets:
                fields = list(fieldset[1]["fields"])
                if "evaluator" in fields:
                    fields[fields.index("evaluator")] = "evaluator_column"
                fieldset[1]["fields"] = tuple(fields)
        return fieldsets

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("activation_map").defer("activation_map__geometry")

    @admin.display(description=_("Evaluator"))
    def evaluator_column(self, obj):
        label = obj.evaluator.choice_label if obj.evaluator else "ND"
        return label

    @admin.display(
        ordering="activation_distance",
        description=mark_safe(
            '<abbr title="Distance d\'activation (m)">Dist. act.</abbr>'
        ),
    )
    def activation_distance_column(self, obj):
        return obj.activation_distance

    @admin.display(ordering="activation_map__name", description="Carte d'activation")
    def activation_map_column(self, obj):
        url = reverse("admin:geodata_map_change", args=[obj.activation_map.pk])
        content = truncatechars(obj.activation_map.name, 45)
        html = f"<a href='{url}'>{content}</a>"
        return mark_safe(html)

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        if obj:
            criterion = obj
            settings_form = criterion.get_settings_form()
            context.update(
                {
                    "settings_form": settings_form,
                    "subtitle": criterion.backend_title,
                }
            )
        res = super().render_change_form(request, context, add, change, form_url, obj)
        return res

    def render_delete_form(self, request, context):
        criterion = context["object"]
        context.update(
            {
                "subtitle": criterion.backend_title,
            }
        )
        return super().render_delete_form(request, context)

    def perimeter_list(self, obj):
        perimeter = obj.perimeter
        return perimeter.backend_name if perimeter else ""

    perimeter_list.short_description = _("Perimeter")


class PerimeterAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "activation_map" in self.fields:
            self.fields["activation_map"].queryset = self.fields[
                "activation_map"
            ].queryset.defer("geometry")

    def get_initial_for_field(self, field, field_name):
        """Prevent Criterion choice to be instanciated.

        In the legacy's version of this function, callable values are, well,
        called.

        But since we have a custom field that should return
        `MoulinetteCriterion` subclasses, we don't want the form to actually
        instanciate those classes.
        """

        value = self.initial.get(field_name, field.initial)
        if callable(value) and not getattr(value, "do_not_call_in_templates", False):
            value = value()
        return value


@admin.register(Perimeter)
class PerimeterAdmin(admin.ModelAdmin):
    list_display = [
        "backend_name",
        "activation_distance_column",
        "departments",
        "is_activated",
    ]
    list_filter = [
        "regulations",
        "is_activated",
        MapDepartmentsListFilter,
    ]
    search_fields = ["backend_name", "name", "activation_map__departments"]
    autocomplete_fields = ["activation_map"]
    form = PerimeterAdminForm

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("activation_map").defer("activation_map__geometry")

    @admin.display(
        ordering="activation_distance",
        description=mark_safe('<abbr title="Distance d\'activation">Dist. act.</abbr>'),
    )
    def activation_distance_column(self, obj):
        return obj.activation_distance

    @admin.display(ordering="activation_map__departments", description=_("Departments"))
    def departments(self, obj):
        return obj.activation_map.departments


class ConfigAmenagementForm(forms.ModelForm):
    regulations_available = forms.MultipleChoiceField(
        label=_("Regulations available"), required=False, choices=REGULATIONS
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "n2000_lotissement_proximity" in self.fields:
            self.fields["n2000_lotissement_proximite"].strip = False

        # Let's not fetch the department geometries when displaying the
        # department select widget
        if "department" in self.fields:
            self.fields["department"].queryset = self.fields[
                "department"
            ].queryset.defer("geometry")


class MoulinetteConfigTemplateForm(forms.ModelForm):
    """Form to edit a MoulinetteTemplate in a ConfigAmenagement.

    We remove every key that is not a real template (autorisation_urba_*, etc.)
    """

    class Meta:
        model = MoulinetteTemplate
        exclude = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        templates = list(list_moulinette_templates())
        self.fields["key"].choices = [
            ("", "---------"),
        ] + list(zip(templates, templates))


class MoulinetteConfigTemplateInline(MoulinetteTemplateInline):
    form = MoulinetteConfigTemplateForm


@admin.register(ConfigAmenagement)
class ConfigAmenagementAdmin(admin.ModelAdmin):
    list_display = ["department", "is_activated", "zh_doubt"]
    form = ConfigAmenagementForm
    inlines = [MoulinetteConfigTemplateInline]
    list_filter = ["is_activated", "zh_doubt"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs.select_related("department")
            .order_by("department__department")
            .defer("department__geometry")
        )


@admin.register(MoulinetteTemplate)
class MoulinetteTemplateAdmin(admin.ModelAdmin):
    list_display = ["config", "key"]
    search_fields = ["content"]


class ConfigHaieAdminForm(forms.ModelForm):
    regulations_available = forms.MultipleChoiceField(
        label=_("Regulations available"), required=False, choices=REGULATIONS
    )

    class Meta:
        model = ConfigHaie
        fields = "__all__"
        widgets = {
            "demarche_simplifiee_pre_fill_config": JSONWidget(
                attrs={"rows": 20, "cols": 80}
            ),
            "demarches_simplifiees_display_fields": JSONWidget(
                attrs={"rows": 20, "cols": 80}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["demarche_simplifiee_pre_fill_config"].help_text = (
            self.get_demarche_simplifiee_pre_fill_config_help_text()
        )

        # Let's not fetch the department geometries when displaying the
        # department select widget
        if "department" in self.fields:
            self.fields["department"].queryset = self.fields[
                "department"
            ].queryset.defer("geometry")

    def get_demarche_simplifiee_pre_fill_config_help_text(self):
        context = {
            "sources": ConfigHaie.get_demarche_simplifiee_value_sources(),
        }
        return render_to_string(
            "admin/moulinette/confighaie/demarche_simplifiee_pre_fill_config_help_text.html",
            context,
        )


@admin.register(ConfigHaie)
class ConfigHaieAdmin(admin.ModelAdmin):
    form = ConfigHaieAdminForm
    list_display = ["department", "is_activated"]
    list_filter = ["is_activated"]
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "department",
                    "is_activated",
                    "regulations_available",
                    "hedge_to_plant_properties_form",
                    "hedge_to_remove_properties_form",
                ],
            },
        ),
        (
            "Régime unique",
            {
                "fields": [
                    "single_procedure",
                    "single_procedure_settings",
                ],
            },
        ),
        (
            "Contenus",
            {
                "fields": [
                    "department_doctrine_html",
                    "contacts_and_links",
                    "hedge_maintenance_html",
                    "natura2000_coordinators_list_url",
                ],
            },
        ),
        (
            "Démarches simplifiées",
            {
                "fields": [
                    "demarche_simplifiee_number",
                    "demarche_simplifiee_pre_fill_config",
                    "demarches_simplifiees_display_fields",
                    "demarches_simplifiees_city_id",
                    "demarches_simplifiees_organization_id",
                    "demarches_simplifiees_pacage_id",
                    "demarches_simplifiees_project_url_id",
                ],
            },
        ),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs.select_related("department")
            .order_by("department__department")
            .defer("department__geometry")
        )


class ActionToTakeForm(forms.ModelForm):
    details = forms.ChoiceField(
        choices=get_template_choices(template_subdir="moulinette/actions_to_take/"),
        required=False,
    )

    class Meta:
        model = ActionToTake
        fields = "__all__"


@admin.register(ActionToTake)
class ActionToTakeAdmin(admin.ModelAdmin):
    form = ActionToTakeForm
    list_display = [
        "slug",
        "type",
        "target",
        "order",
    ]
