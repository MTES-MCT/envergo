from django.contrib.auth import get_user_model
from factory import Faker
from factory.django import DjangoModelFactory, Password


class UserFactory(DjangoModelFactory):
    email = Faker("email")
    name = Faker("name")
    password = Password("password")
    access_amenagement = True
    access_haie = False

    class Meta:
        model = get_user_model()
        django_get_or_create = ["email"]
