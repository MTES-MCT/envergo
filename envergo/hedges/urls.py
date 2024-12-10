from django.urls import path

from envergo.hedges.views import HedgeInput

urlpatterns = [
    path("input/", HedgeInput.as_view(), name="input_hedges"),
    path("input/<uuid:id>/", HedgeInput.as_view(), name="input_hedges"),
    path("<str:mode>/", HedgeInput.as_view(), name="input_hedges_mode"),
    path("<str:mode>/<uuid:id>/", HedgeInput.as_view(), name="input_hedges_mode"),
]
