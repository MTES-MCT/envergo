from django.urls import include, path

from .urls import auth_patterns as common_auth_patterns
from .urls import urlpatterns as common_urlpatterns

auth_patterns = common_auth_patterns

urlpatterns = [
    path("", include("envergo.pages.urls_haie")),
] + common_urlpatterns
