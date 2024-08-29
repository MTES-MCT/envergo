from django.contrib.sites.models import Site
from factory.django import DjangoModelFactory


class SiteFactory(DjangoModelFactory):
    class Meta:
        model = Site

    domain = "testserver"
    name = "testserver"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        instance, created = model_class.objects.get_or_create(*args, **kwargs)
        return instance
