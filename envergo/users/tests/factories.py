from django.contrib.auth import get_user_model
from factory import Faker, Trait
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

    class Params:
        is_envergo_user = Trait(
            is_active=True,
            access_amenagement=True,
            access_haie=False,
        )
        is_envergo_inactive_user = Trait(
            is_envergo_user=True,
            is_active=False,
        )
        is_haie_user = Trait(
            is_active=True,
            access_amenagement=False,
            access_haie=True,
        )
        is_haie_inactive_user = Trait(
            is_haie_user=True,
            is_active=False,
        )
        is_haie_instructor = Trait(
            is_haie_user=True,
            is_instructor=True,
        )
