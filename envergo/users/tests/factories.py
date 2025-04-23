import factory
from django.contrib.auth import get_user_model
from factory import Faker
from factory.django import DjangoModelFactory, Password

from envergo.geodata.tests.factories import DepartmentFactory


class UserFactory(DjangoModelFactory):
    email = Faker("email")
    name = Faker("name")
    password = Password("password")
    is_confirmed_by_admin = False
    access_amenagement = True
    access_haie = False

    class Meta:
        model = get_user_model()
        django_get_or_create = ["email"]

    @factory.post_generation
    def create_user(obj, create, extracted, **kwargs):
        department_44 = DepartmentFactory.create()

        if create:
            obj.departments.add(department_44)
