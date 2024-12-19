import pytest

from envergo.hedges.tests.factories import (
    HedgeDataFactory,
    HedgeFactory,
    SpeciesFactory,
)

pytestmark = pytest.mark.django_db


def test_species_are_filtered_by_hedge_type():
    s1 = SpeciesFactory(hedge_types=["degradee"])
    s2 = SpeciesFactory(hedge_types=["degradee"])
    s3 = SpeciesFactory(hedge_types=["arbustive"])
    hedge = HedgeFactory(additionalData__typeHaie="degradee")
    hedges = HedgeDataFactory(hedges=[hedge])

    hedges_species = hedges.get_all_species()
    assert s1 in hedges_species
    assert s2 in hedges_species
    assert s3 not in hedges_species

    hedge = HedgeFactory(additionalData__typeHaie="arbustive")
    hedges = HedgeDataFactory(hedges=[hedge])
    hedges_species = hedges.get_all_species()
    assert s1 not in hedges_species
    assert s2 not in hedges_species
    assert s3 in hedges_species


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
    all_species = hedges.get_all_species()
    assert set(all_species) == set([s2, s3, s4])
