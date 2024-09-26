from django.urls import path

from envergo.hedges.views import HedgeInput, SaveHedgeDataView

urlpatterns = [
    path("input/", HedgeInput.as_view(), name="input_hedges"),
    path("save/", SaveHedgeDataView.as_view(), name="save_hedges"),
]
