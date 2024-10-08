from django import forms
from django.contrib import admin
from django.template.defaultfilters import truncatechars
from django.urls import reverse
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.geodata.admin import DepartmentsListFilter
from envergo.moulinette.models import (
    REGULATIONS,
    ConfigAmenagement,
    ConfigHaie,
    Criterion,
    MoulinetteTemplate,
    Perimeter,
    Regulation,
)
from envergo.moulinette.regulations import CriterionEvaluator
from envergo.moulinette.utils import list_moulinette_templates


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


@admin.register(Regulation)
class RegulationAdmin(admin.ModelAdmin):
    list_display = [
        "get_regulation_display",
        "regulation_slug",
        "has_perimeters",
        "weight",
    ]
    list_editable = ["weight"]

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
        "perimeter",
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
        "regulation",
        "activation_distance_column",
        "departments",
        "is_activated",
    ]
    list_filter = ["regulation", "is_activated", MapDepartmentsListFilter]
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

    def clean_criteria_values(self):
        """Ensure an empty value can be converted to an empty json dict."""
        value = self.cleaned_data["criteria_values"]
        value = value or dict()
        return value


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
        self.fields["key"].choices = zip(templates, templates)


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


@admin.register(ConfigHaie)
class ConfigHaieAdmin(admin.ModelAdmin):
    list_display = ["department", "is_activated", "department_guichet_unique_url"]
    list_filter = ["is_activated"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return (
            qs.select_related("department")
            .order_by("department__department")
            .defer("department__geometry")
        )
