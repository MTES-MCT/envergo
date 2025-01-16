import json

from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView

from envergo.hedges.forms import HedgeToPlantDataForm, HedgeToRemoveDataForm
from envergo.hedges.models import HedgeData
from envergo.hedges.services import HedgeEvaluator


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(xframe_options_sameorigin, name="dispatch")
class HedgeInput(DetailView):
    """Create or update a hedge input."""

    template_name = "hedges/input.html"
    model = HedgeData
    context_object_name = "hedge_data"
    pk_url_kwarg = "id"

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)

        # This happens when no uuid is passed in the url
        except AttributeError:
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mode = self.kwargs.get("mode", "removal")

        context["mode"] = mode
        hedge_data = json.dumps(self.object.data) if self.object else "[]"
        context["hedge_data_json"] = hedge_data
        context["hedge_to_plant_data_form"] = HedgeToPlantDataForm(prefix="plantation")
        context["hedge_to_remove_data_form"] = HedgeToRemoveDataForm(prefix="removal")
        context["minimum_length_to_plant"] = (
            self.object.minimum_length_to_plant() if self.object else 0
        )

        if mode == "removal":
            context["matomo_custom_url"] = self.request.build_absolute_uri(
                reverse("moulinette_saisie_d")
            )
        elif mode == "plantation":
            context["matomo_custom_url"] = self.request.build_absolute_uri(
                reverse("moulinette_saisie_p")
            )
        elif mode == "read_only":
            context["matomo_custom_url"] = self.request.build_absolute_uri(
                reverse("petition_project_hedges")
            )

        return context

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            hedge_data, created = HedgeData.objects.update_or_create(
                id=kwargs.get("id"), defaults={"data": data}
            )
            response_data = {
                "input_id": str(hedge_data.id),
                "hedges_to_plant": len(hedge_data.hedges_to_plant()),
                "length_to_plant": hedge_data.length_to_plant(),
                "hedges_to_remove": len(hedge_data.hedges_to_remove()),
                "length_to_remove": hedge_data.length_to_remove(),
                "lineaire_detruit_pac": hedge_data.lineaire_detruit_pac_including_alignement(),
            }
            status_code = 201 if created else 200
            return JsonResponse(response_data, status=status_code)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


class HedgeQualityView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            hedge_data = HedgeData(data=data)
            evaluator = HedgeEvaluator(hedge_data=hedge_data)
            evaluation = evaluator.evaluate()
            return JsonResponse(evaluation, status=200, safe=False)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
