import json

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, TemplateView

from envergo.hedges.models import HedgeData


class HedgeInput(TemplateView):
    template_name = "hedges/input.html"


@method_decorator(csrf_exempt, name="dispatch")
class SaveHedgeDataView(CreateView):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            hedge_data = HedgeData.objects.create(data=data)
            return JsonResponse({"id": str(hedge_data.id)}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
