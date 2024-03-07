from django import forms
from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from envergo.geodata.admin import DepartmentsListFilter
from envergo.moulinette.models import (
    REGULATIONS,
    Criterion,
    MoulinetteConfig,
    MoulinetteTemplate,
    Perimeter,
    Regulation,
)
from envergo.moulinette.regulations import CriterionEvaluator


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
    list_display = ["get_regulation_display", "regulation_slug", "has_perimeters"]

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


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = [
        "backend_title",
        "regulation",
        "activation_map",
        "activation_distance",
        "evaluator_column",
    ]
    readonly_fields = ["unique_slug"]
    autocomplete_fields = ["activation_map"]
    form = CriterionAdminForm
    search_fields = [
        "backend_title",
        "title",
        "regulation__regulation",
        "activation_map__name",
    ]
    list_filter = ["regulation", MapDepartmentsListFilter, "evaluator"]
    sortable_by = ["backend_title", "activation_map", "activation_distance"]

    class Media:
        css = {
            "all": ["css/project_admin.css"],
        }

    @admin.display(description=_("Evaluator"))
    def evaluator_column(self, obj):
        label = obj.evaluator.choice_label if obj.evaluator else "ND"
        return label

    def render_change_form(
        self, request, context, add=False, change=False, form_url="", obj=None
    ):
        if obj:
            criterion = obj
            settings_form = criterion.get_settings_form()
            context.update({"settings_form": settings_form})
        res = super().render_change_form(request, context, add, change, form_url, obj)
        return res


class PerimeterAdminForm(forms.ModelForm):
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

    @admin.display(
        ordering="activation_distance",
        description=mark_safe('<abbr title="Distance d\'activation">Dist. act.</abbr>'),
    )
    def activation_distance_column(self, obj):
        return obj.activation_distance

    @admin.display(ordering="activation_map__departments", description=_("Departments"))
    def departments(self, obj):
        return obj.activation_map.departments


class MoulinetteConfigForm(forms.ModelForm):
    regulations_available = forms.MultipleChoiceField(
        label=_("Regulations available"), required=False, choices=REGULATIONS
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["n2000_lotissement_proximite"].strip = False


class MoulinetteTemplateInline(admin.StackedInline):
    model = MoulinetteTemplate
    extra = 0


@admin.register(MoulinetteConfig)
class MoulinetteConfigAdmin(admin.ModelAdmin):
    list_display = ["department", "is_activated"]
    form = MoulinetteConfigForm
    inlines = [MoulinetteTemplateInline]
    list_filter = ["is_activated"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.order_by("department__department")


@admin.register(MoulinetteTemplate)
class MoulinetteTemplateAdmin(admin.ModelAdmin):
    list_display = ["config", "key"]
    search_fields = ["content"]
