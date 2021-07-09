from django import forms
from django.contrib import admin

from envergo.evaluations.forms import EvaluationFormMixin
from envergo.evaluations.models import Evaluation


class EvaluationAdminForm(EvaluationFormMixin, forms.ModelForm):
    pass


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ["application_number", "created_at"]
    form = EvaluationAdminForm
