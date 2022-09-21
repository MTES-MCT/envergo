from django.urls import path
from django.utils.translation import gettext_lazy as _

from envergo.moulinette.views import MoulinetteHome, MoulinetteResults

urlpatterns = [
    path("", MoulinetteHome.as_view(), name="moulinette_home"),
    path(_("results/"), MoulinetteResults.as_view(), name="moulinette_results"),
]
