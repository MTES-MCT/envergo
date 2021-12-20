from django.urls import path

from envergo.stats.views import StatsView

urlpatterns = [
    path("", StatsView.as_view(), name="stats"),
]
