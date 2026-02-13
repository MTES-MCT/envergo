from django.urls import path

from envergo.demos.views import CatchmentArea, HedgeDensity, HedgeDensityBuffer

urlpatterns = [
    path("densite-haie/", HedgeDensity.as_view(), name="demo_density"),
    path("densite-haie-2/", HedgeDensityBuffer.as_view(), name="demo_density_buffer"),
    path("bassin-versant/", CatchmentArea.as_view(), name="demo_catchment_area"),
]
