from django.urls import path

from envergo.haies.views import Saisie

urlpatterns = [
    path("saisie/", Saisie.as_view(), name="saisie_haie"),
]
