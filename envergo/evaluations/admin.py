from django.contrib import admin

from envergo.evaluations.models import Evaluation


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ["application_number"]
