import pytest
from django.urls import reverse

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.models import DOSSIER_STATES
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("config.urls_haie")]


@pytest.fixture(autouse=True)
def fake_haie_settings(settings):
    settings.ENVERGO_HAIE_DOMAIN = "testserver"
    settings.ENVERGO_AMENAGEMENT_DOMAIN = "otherserver"


def test_petition_project_list_num_queries(
    haie_instructor_44, admin_user, client, site, django_assert_max_num_queries
):
    """Test num queries for project list"""

    # GIVEN several projects
    DCConfigHaieFactory()
    PetitionProjectFactory.create_batch(
        15, demarche_numerique_state=DOSSIER_STATES.prefilled
    )
    project_list_url = reverse("petition_project_list")

    # WHEN admin user visit project list
    client.force_login(admin_user)
    with django_assert_max_num_queries(13):
        client.get(project_list_url)

    # WHEN haie_instructor_44 visit project list
    client.force_login(haie_instructor_44)
    with django_assert_max_num_queries(15):
        client.get(project_list_url)
