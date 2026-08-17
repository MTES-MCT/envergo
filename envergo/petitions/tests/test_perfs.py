import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.models import DOSSIER_STATES
from envergo.petitions.tests.factories import PetitionProjectFactory

pytestmark = [pytest.mark.django_db, pytest.mark.urls("config.urls_haie")]


def test_petition_project_list_query_count_is_constant(
    haie_instructor_44, client, site
):
    """Rendering the list must not run per-project queries."""
    DCConfigHaieFactory()
    for _ in range(3):
        PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.prefilled)

    client.force_login(haie_instructor_44)
    url = reverse("petition_project_list")
    client.get(url)  # warm up session-related queries

    with CaptureQueriesContext(connection) as with_3_projects:
        client.get(url)

    for _ in range(5):
        PetitionProjectFactory(demarche_numerique_state=DOSSIER_STATES.prefilled)

    with CaptureQueriesContext(connection) as with_8_projects:
        client.get(url)

    assert len(with_8_projects) == len(with_3_projects)
