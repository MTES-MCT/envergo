import random
from string import ascii_uppercase

import factory
from factory import fuzzy
from factory.django import DjangoModelFactory

from envergo.geodata.models import Parcel


def generate_section():
    length = random.randint(1, 2)
    section = "".join(random.choices(ascii_uppercase, k=length))
    return section


class ParcelFactory(DjangoModelFactory):
    class Meta:
        model = Parcel

    commune = fuzzy.FuzzyInteger(10000, 90000)
    section = factory.LazyFunction(generate_section)
    prefix = "000"
    order = fuzzy.FuzzyInteger(1, 9999)
