from django.contrib.sites.models import Site
from factory.django import DjangoModelFactory


class SiteFactory(DjangoModelFactory):
    class Meta:
        model = Site

    domain = "testserver"
    name = "testserver"
