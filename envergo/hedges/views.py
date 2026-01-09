import json
import logging
from urllib.parse import urlparse

from django.http import JsonResponse, QueryDict
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView
from django.views.generic.edit import FormMixin, FormView

from envergo.analytics.utils import update_url_with_matomo_params
from envergo.decorators.csp import csp_override, csp_report_only_override
from envergo.hedges.forms import HedgeToPlantPropertiesForm, HedgeToRemovePropertiesForm
from envergo.hedges.models import HedgeData
from envergo.hedges.services import PlantationEvaluator
from envergo.moulinette.models import ConfigHaie
from envergo.moulinette.views import MoulinetteMixin

logger = logging.getLogger(__name__)


# VueJS, in the full build, uses the `eval` js method to compile it's templates
# This make it incompatible with csp unless we allow "unsafe-eval", which makes csp
# pretty much useless.
# To fix the problem, we should use the runtime vue build that requires that all templates are pre-compiled into
# render functions
# A temporary fix is to disable csp for this page, which is not ideal.
@method_decorator(
    csp_override(config={}),
    name="get",
)
@method_decorator(
    csp_report_only_override(config={}),
    name="get",
)
@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(xframe_options_sameorigin, name="dispatch")
class HedgeInput(MoulinetteMixin, FormMixin, DetailView):
    """Create, update or display a hedge input."""

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

    def get_hedge_to_plant_data_form(self, config=None):
        """Return hedge data form to plant from config"""
        data_form = HedgeToPlantPropertiesForm(prefix="plantation")
        if config:
            data_form = import_string(config.hedge_to_plant_properties_form)(
                prefix="plantation"
            )

        return data_form

    def get_hedge_to_remove_data_form(self, config=None):
        """Return hedge data form to remove from config"""
        data_form = HedgeToRemovePropertiesForm(prefix="removal")
        if config:
            data_form = import_string(config.hedge_to_remove_properties_form)(
                prefix="removal"
            )

        return data_form

    def get_conditions_url(self, mode="plantation"):
        """Return conditions url to display plantation conditions"""
        conditions_url = ""
        if mode == "removal" or mode == "plantation":
            conditions_url = (
                f'{reverse("hedge_conditions")}?{self.request.GET.urlencode()}'
            )

        if mode == "read_only":
            # params are in petition project
            if self.object:
                petition_project = self.object.petitionproject_set.first()
                query_string = urlparse(petition_project.moulinette_url)
                query = QueryDict(query_string.query)
                conditions_url = reverse("hedge_conditions") + "?" + query.urlencode()
        return conditions_url

    def get_matomo_custom_url(self, mode="removal"):
        """Return matomo custom url depending on mode"""
        matomo_custom_url = ""
        if mode == "removal":
            matomo_custom_url = self.request.build_absolute_uri(
                reverse("moulinette_saisie_d")
            )
        if mode == "plantation":
            matomo_custom_url = self.request.build_absolute_uri(
                reverse("moulinette_saisie_p")
            )
        elif mode == "read_only":
            source_page = self.request.GET.get("source")
            if source_page == "consultation":
                matomo_custom_url = self.request.build_absolute_uri(
                    reverse("petition_project_hedges")
                )
            elif source_page == "instruction":
                matomo_custom_url = self.request.build_absolute_uri(
                    reverse("instructor_view_hedges")
                )

        return matomo_custom_url

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        config = None
        department = self.kwargs.get("department", "")
        context["department"] = department
        if department:
            config = ConfigHaie.objects.filter(
                department__department=department
            ).first()

        context["hedge_to_plant_data_form"] = self.get_hedge_to_plant_data_form(config)
        context["hedge_to_remove_data_form"] = self.get_hedge_to_remove_data_form(
            config
        )

        if self.object and self.moulinette.is_valid():
            plantation_evaluator = PlantationEvaluator(self.moulinette, self.object)
            context.update(plantation_evaluator.get_context())
        else:
            context["minimum_length_to_plant"] = 0

        # TODO Refactor removal and plantation to be different views
        if self.object:
            context["hedge_data_json"] = json.dumps(self.object.data)
        else:
            context["hedge_data_json"] = "[]"

        mode = self.kwargs.get("mode", "removal")
        context["mode"] = mode
        context["matomo_custom_url"] = update_url_with_matomo_params(
            self.get_matomo_custom_url(mode), self.request
        )
        context["hedge_conditions_url"] = self.get_conditions_url(mode)
        context["is_alternative"] = bool(self.request.GET.get("alternative", False))

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
            logger.exception(e)
            return JsonResponse({"error": "An internal error has occurred"}, status=500)

    def log_moulinette_event(self, moulinette, context, **kwargs):
        return


class HedgeConditionsView(MoulinetteMixin, FormView):
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
        try:
            data = json.loads(request.body)
            hedge_data = HedgeData(data=data)
            evaluator = PlantationEvaluator(self.moulinette, hedge_data)
            evaluator.evaluate()
            return JsonResponse(evaluator.to_json(), status=200, safe=False)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            logger.exception(e)
            return JsonResponse({"error": "An internal error has occurred"}, status=500)

    def log_moulinette_event(self, moulinette, context, **kwargs):
        return
