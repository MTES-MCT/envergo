import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, TemplateView

from envergo.hedges.models import HedgeData


@method_decorator(xframe_options_sameorigin, name="dispatch")
class HedgeInput(TemplateView):
    template_name = "hedges/input.html"


@method_decorator(csrf_exempt, name="dispatch")
class SaveHedgeDataView(CreateView):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            hedge_data = HedgeData.objects.create(data=data)
            response_data = {
                "input_id": str(hedge_data.id),
                "hedges_to_plant": len(hedge_data.hedges_to_plant()),
                "length_to_plant": sum(h.length for h in hedge_data.hedges_to_plant()),
                "hedges_to_remove": len(hedge_data.hedges_to_remove()),
                "length_to_remove": sum(
                    h.length for h in hedge_data.hedges_to_remove()
                ),
            }
            return JsonResponse(response_data, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
