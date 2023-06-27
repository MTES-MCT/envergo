from django import forms
from django.contrib import admin

from envergo.geodata.models import Map
from envergo.moulinette.models import (
    Contact,
    Criterion,
    MoulinetteConfig,
    Perimeter,
    Regulation,
)
from envergo.moulinette.regulations import MoulinetteCriterion


@admin.register(Regulation)
class RegulationAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "perimeter", "activation_distance"]
    prepopulated_fields = {"slug": ["title"]}


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "regulation", "perimeter", "activation_distance"]
    prepopulated_fields = {"slug": ["title"]}


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
        if callable(value) and not issubclass(value, MoulinetteCriterion):
            value = value()
        return value


@admin.register(Perimeter)
class PerimeterAdmin(admin.ModelAdmin):
    form = PerimeterAdminForm

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit map choices to those with empty "map type".

        Maps for wetlands or flood zones are not used for perimeters.

        Also, I find it weird that there is no better way to filter foreign key
        choices.
        """
        if db_field.name == "map":
            kwargs["queryset"] = Map.objects.filter(map_type="")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class MoulinetteConfigForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["n2000_lotissement_proximite"].strip = False


@admin.register(MoulinetteConfig)
class MoulinetteConfigAdmin(admin.ModelAdmin):
    list_display = ["department", "is_activated"]
    form = MoulinetteConfigForm


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ["name", "perimeter", "url"]
    fields = ["perimeter", "name", "url", "address_md"]
