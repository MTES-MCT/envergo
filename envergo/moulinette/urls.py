from django.urls import path

from envergo.moulinette.views import MoulinetteHome

urlpatterns = [
    path("", MoulinetteHome.as_view(), name="moulinette_home"),
]
