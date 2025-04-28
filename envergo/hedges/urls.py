from django.urls import path

from envergo.hedges.views import HedgeConditionsView, HedgeInput

urlpatterns = [
    path("conditions/", HedgeConditionsView.as_view(), name="hedge_conditions"),
    path("<str:department>/<str:mode>/", HedgeInput.as_view(), name="input_hedges"),
    path(
        "<str:department>/<str:mode>/<uuid:id>/",
        HedgeInput.as_view(),
        name="input_hedges",
    ),
]
