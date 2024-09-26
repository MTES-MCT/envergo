from django.urls import path

from envergo.haies.views import Saisie, SaveHedgeDataView

urlpatterns = [
    path("saisie/", Saisie.as_view(), name="input_hedges"),
    path("save/", SaveHedgeDataView.as_view(), name="save_hedges"),
]
