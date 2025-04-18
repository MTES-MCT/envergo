from unittest.mock import patch

import pytest
from shapely import centroid

from envergo.hedges.models import Species
from envergo.hedges.tests.factories import (
    HedgeDataFactory,
    HedgeFactory,
    SpeciesFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cleanup():
    # Remove demo species
    Species.objects.all().delete()


def test_species_are_filtered_by_hedge_type():
    s1 = SpeciesFactory(hedge_types=["degradee"])
    s2 = SpeciesFactory(hedge_types=["degradee"])
    s3 = SpeciesFactory(hedge_types=["arbustive"])
    hedge = HedgeFactory(additionalData__typeHaie="degradee")
    hedges = HedgeDataFactory(hedges=[hedge])

    hedges_species = hedges.get_hedge_species()
    assert s1 in hedges_species
    assert s2 in hedges_species
    assert s3 not in hedges_species

    hedge = HedgeFactory(additionalData__typeHaie="arbustive")
    hedges = HedgeDataFactory(hedges=[hedge])
    hedges_species = hedges.get_hedge_species()
    assert s1 not in hedges_species
    assert s2 not in hedges_species
    assert s3 in hedges_species


@patch("envergo.hedges.models.get_department_from_coords")
def test_hedges_has_centroid_and_department(mock_get_department):
    hedge = HedgeDataFactory()
    centroid_to_remove = hedge.get_centroid_to_remove()
    centroid_computed = centroid(hedge.hedges_to_remove()[0].geometry)

    assert centroid_to_remove == centroid_computed

    mock_get_department.return_value = "34"
    department = hedge.get_department()

    assert department == "34"


def test_species_are_filtered_by_hedge_features():
    s1 = SpeciesFactory(proximite_mare=True, vieil_arbre=True)
    s2 = SpeciesFactory(proximite_mare=True, vieil_arbre=False)
    s3 = SpeciesFactory(proximite_mare=False, vieil_arbre=True)
    s4 = SpeciesFactory(proximite_mare=False, vieil_arbre=False)

    hedge = HedgeFactory(
        additionalData__proximiteMare=False, additionalData__vieilArbre=False
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s4])

    hedge = HedgeFactory(
        additionalData__proximiteMare=True, additionalData__vieilArbre=False
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s2, s4])

    hedge = HedgeFactory(
        additionalData__proximiteMare=False, additionalData__vieilArbre=True
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s3, s4])

    hedge = HedgeFactory(
        additionalData__proximiteMare=True, additionalData__vieilArbre=True
    )
    hedge_species = hedge.get_species()
    assert set(hedge_species) == set([s1, s2, s3, s4])


def test_multiple_hedges_combine_their_species():
    _ = SpeciesFactory(proximite_mare=True, vieil_arbre=True)
    s2 = SpeciesFactory(proximite_mare=True, vieil_arbre=False)
    s3 = SpeciesFactory(proximite_mare=False, vieil_arbre=True)
    s4 = SpeciesFactory(proximite_mare=False, vieil_arbre=False)

    hedge1 = HedgeFactory(
        additionalData__proximiteMare=True, additionalData__vieilArbre=False
    )
    hedge_species = hedge1.get_species()
    assert set(hedge_species) == set([s2, s4])

    hedge2 = HedgeFactory(
        additionalData__proximiteMare=False, additionalData__vieilArbre=True
    )
    hedge_species = hedge2.get_species()
    assert set(hedge_species) == set([s3, s4])

    hedges = HedgeDataFactory(hedges=[hedge1, hedge2])
    all_species = hedges.get_hedge_species()
    assert set(all_species) == set([s2, s3, s4])
