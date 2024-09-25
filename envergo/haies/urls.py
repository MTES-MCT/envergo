from django.urls import path

from envergo.haies.views import Saisie, SaveHedgeDataView

urlpatterns = [
    path("saisie/", Saisie.as_view(), name="saisie_haie"),
    path("persist/", SaveHedgeDataView.as_view(), name="persist_hedges"),
]
