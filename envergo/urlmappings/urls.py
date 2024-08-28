from django.urls import path

from envergo.urlmappings.views import UrlMappingCreateView

urlpatterns = [
    path("create/", UrlMappingCreateView.as_view(), name="urlmapping_create"),
]
