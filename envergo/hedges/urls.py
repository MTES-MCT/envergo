from django.urls import path

from envergo.hedges.views import HedgeInput, HedgeQualityView

urlpatterns = [
    path("qualite/", HedgeQualityView.as_view(), name="hedge_quality"),
    path("<str:department>/<str:mode>/", HedgeInput.as_view(), name="input_hedges"),
    path(
        "<str:department>/<str:mode>/<uuid:id>/",
        HedgeInput.as_view(),
        name="input_hedges",
    ),
]
