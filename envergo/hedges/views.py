import json

from django.http import JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView

from envergo.hedges.models import HedgeData


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

        hedge_data = json.dumps(self.object.data) if self.object else "[]"
        context["hedge_data_json"] = hedge_data

        if self.object:
            save_url = reverse("input_hedges", args=[self.object.id])
        else:
            save_url = reverse("input_hedges")
        context["save_url"] = save_url
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
                "length_to_plant": sum(h.length for h in hedge_data.hedges_to_plant()),
                "hedges_to_remove": len(hedge_data.hedges_to_remove()),
                "length_to_remove": sum(
                    h.length for h in hedge_data.hedges_to_remove()
                ),
            }
            status_code = 201 if created else 200
            return JsonResponse(response_data, status=status_code)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
