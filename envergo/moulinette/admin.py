from django import forms
from django.contrib import admin

from envergo.moulinette.models import MoulinetteConfig, Perimeter
from envergo.moulinette.regulations import MoulinetteCriterion


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


@admin.register(MoulinetteConfig)
class MoulinetteConfigAdmin(admin.ModelAdmin):
    list_display = ["department", "is_activated"]
