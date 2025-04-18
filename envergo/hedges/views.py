import json

from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView
from django.views.generic.edit import FormMixin, FormView

from envergo.hedges.forms import HedgeToPlantPropertiesForm, HedgeToRemovePropertiesForm
from envergo.hedges.models import HedgeData
from envergo.hedges.services import HedgeEvaluator, PlantationEvaluator
from envergo.moulinette.models import ConfigHaie
from envergo.moulinette.views import MoulinetteMixin


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(xframe_options_sameorigin, name="dispatch")
class HedgeInput(MoulinetteMixin, FormMixin, DetailView):
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

        context["hedge_to_plant_data_form"] = HedgeToPlantPropertiesForm(
            prefix="plantation"
        )
        context["hedge_to_remove_data_form"] = HedgeToRemovePropertiesForm(
            prefix="removal"
        )

        department = self.kwargs.get("department", "")
        context["department"] = department
        if department:
            config = ConfigHaie.objects.filter(
                department__department=department
            ).first()
            if config:
                context["hedge_to_plant_data_form"] = import_string(
                    config.hedge_to_plant_properties_form
                )(prefix="plantation")
                context["hedge_to_remove_data_form"] = import_string(
                    config.hedge_to_remove_properties_form
                )(prefix="removal")

        if self.object and "moulinette" in context:
            moulinette = context["moulinette"]
            plantation_evaluator = PlantationEvaluator(moulinette, self.object)
            context["minimum_length_to_plant"] = (
                plantation_evaluator.minimum_length_to_plant()
            )
            context["is_removing_pac"] = len(self.object.hedges_to_remove_pac()) > 0
        else:
            context["minimum_length_to_plant"] = 0
            context["is_removing_pac"] = False

        # TODO Refactor removal and plantation to be different views
        if self.object:
            context["hedge_data_json"] = json.dumps(self.object.data)
        else:
            context["hedge_data_json"] = "[]"

        mode = self.kwargs.get("mode", "removal")
        context["mode"] = mode
        if mode == "removal":
            context["matomo_custom_url"] = self.request.build_absolute_uri(
                reverse("moulinette_saisie_d")
            )
        elif mode == "plantation":
            context["matomo_custom_url"] = self.request.build_absolute_uri(
                reverse("moulinette_saisie_p")
            )
        elif mode == "read_only":
            source_page = self.request.GET.get("source_page")
            if source_page == "consultation":
                context["matomo_custom_url"] = self.request.build_absolute_uri(
                    reverse("petition_project_hedges")
                )
            elif source_page == "instruction":
                context["matomo_custom_url"] = self.request.build_absolute_uri(
                    reverse("instructor_view_hedges")
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

    def log_moulinette_event(self, moulinette, context, **kwargs):
        return


class HedgeQualityView(MoulinetteMixin, FormView):
    def get_form_kwargs(self):
        """Return the moulinette form args.

        Even though the request is a POST, the moulinette arguments are passed
        in the GET parameters. That's why we had to override this method.
        """
        kwargs = {
            "initial": self.get_initial(),
            "prefix": self.get_prefix(),
            "data": self.request.GET,
        }
        return kwargs

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        moulinette = context["moulinette"]

        try:
            data = json.loads(request.body)
            hedge_data = HedgeData(data=data)
            plantation_evaluator = PlantationEvaluator(moulinette, hedge_data)
            evaluator = HedgeEvaluator(plantation_evaluator)
            evaluation = evaluator.evaluate()
            return JsonResponse(evaluation, status=200, safe=False)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    def log_moulinette_event(self, moulinette, context, **kwargs):
        return
