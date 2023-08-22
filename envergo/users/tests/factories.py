from django.contrib.auth import get_user_model
from factory import Faker
from factory.django import DjangoModelFactory, Password


class UserFactory(DjangoModelFactory):
    email = Faker("email")
    name = Faker("name")
    password = Password("password")

    class Meta:
        model = get_user_model()
        django_get_or_create = ["email"]
