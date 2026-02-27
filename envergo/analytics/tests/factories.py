import datetime

import factory
from factory import Faker
from factory.django import DjangoModelFactory

from envergo.analytics.models import Event
from envergo.contrib.sites.tests.factories import SiteFactory


class EventFactory(DjangoModelFactory):
    category = Faker("word")
    event = Faker("word")
    session_key = Faker("sha1")
    date_created = Faker(
        "date_time_between",
        start_date="-1m",
        end_date="now",
        tzinfo=datetime.timezone.utc,
    )

    class Meta:
        model = Event


class EvalreqEventFactory(EventFactory):
    category = "evaluation"
    event = "request"
    site = factory.SubFactory(SiteFactory)


class SimulationEventFactory(EventFactory):
    category = "simulateur"
    event = "soumission"
    site = factory.SubFactory(SiteFactory)
