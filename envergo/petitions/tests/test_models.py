from urllib.parse import parse_qs, urlparse

import pytest

from envergo.moulinette.tests.factories import DCConfigHaieFactory
from envergo.petitions.tests.factories import PetitionProjectFactory, SimulationFactory

pytestmark = pytest.mark.django_db


def test_set_department_on_save():
    DCConfigHaieFactory()
    petition_project = PetitionProjectFactory()
    assert petition_project.department.department == "44"


def test_form_url_adds_alternative_param():
    """form_url appends alternative=true to the query string."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    simulation = SimulationFactory(project=project)

    # Check that "alternative" is not already in the initial url
    url = simulation.moulinette_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "alternative" not in params

    url = simulation.form_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert params["alternative"] == ["true"]


def test_form_url_does_not_duplicate_alternative_param():
    """form_url replaces an existing alternative param instead of appending a second one."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Create a simulation whose moulinette_url already contains alternative=true
    moulinette_url = project.moulinette_url + "&alternative=true"
    simulation = SimulationFactory(project=project, moulinette_url=moulinette_url)
    url = simulation.form_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Should have exactly one value, not two
    assert params["alternative"] == ["true"]


@pytest.mark.haie
def test_result_url_adds_alternative_param():
    """result_url appends alternative=true for new simulations."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    simulation = SimulationFactory(project=project, is_active=False)
    url = simulation.result_url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert params["alternative"] == ["true"]


@pytest.mark.haie
def test_result_url_active_returns_project_url():
    """result_url points to the project page (without alternative param) for active simulations."""
    DCConfigHaieFactory()
    project = PetitionProjectFactory()
    # Deactivate the initial simulation created by the factory
    project.simulations.update(is_active=False)
    simulation = SimulationFactory(project=project, is_active=True)
    url = simulation.result_url
    assert f"/projet/{project.reference}/" in url
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert "alternative" not in params
