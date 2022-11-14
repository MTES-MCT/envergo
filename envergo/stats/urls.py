from django.urls import path
from django.views.generic import RedirectView

urlpatterns = [
    path(
        "",
        RedirectView.as_view(url="https://sites.google.com/view/stats-envergo/"),
        name="stats",
    ),
]
