from unittest.mock import patch

import pytest
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import IntegrityError, transaction
from shapely import centroid

from envergo.geodata.conftest import aisne_map, calvados_map  # noqa
from envergo.geodata.tests.factories import (
    DepartmentFactory,
    MapFactory,
    ZoneFactory,
    acy_polygon,
    herault_multipolygon,
    limé_polygon,
)
from envergo.hedges.models import HedgeList, Species
from envergo.hedges.tests.factories import (
    HedgeDataFactory,
    HedgeFactory,
    SpeciesFactory,
    SpeciesHabitatFactory,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def cleanup():
    # Remove demo species
    Species.objects.all().delete()


@pytest.fixture
def aisne_hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.571258332741955, "lng": 3.613762429205578},
                    {"lat": 49.57123937690368, "lng": 3.613863328804695},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": True,
                    "proximite_mare": False,
                    "sur_parcelle_pac": True,
                    "ripisylve": False,
                    "connexion_boisement": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.57154029531499, "lng": 3.6139268852842137},
                    {"lat": 49.57134548129514, "lng": 3.6138314019310296},
                ],
                "additionalData": {
                    "type_haie": "arbustive",
                    "vieil_arbre": False,
                    "proximite_mare": True,
                    "sur_parcelle_pac": False,
                    "ripisylve": True,
                    "connexion_boisement": False,
                },
            },
        ]
    )
    return hedge_data


@pytest.fixture
def calvados_hedge_data():
    hedge_data = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.18748081945032, "lng": -0.3705271743228811},
                    {"lat": 49.18672325114213, "lng": -0.37134275747315654},
                ],
                "additionalData": {
                    "type_haie": "degradee",
                    "vieil_arbre": True,
                    "proximite_mare": True,
                    "sur_parcelle_pac": True,
                    "ripisylve": False,
                    "connexion_boisement": False,
                    "sur_talus": True,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.18748081945032, "lng": -0.3705271743228811},
                    {"lat": 49.18672325114213, "lng": -0.37134275747315654},
                ],
                "additionalData": {
                    "type_haie": "alignement",
                    "vieil_arbre": True,
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "ripisylve": False,
                    "connexion_boisement": True,
                },
            },
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 49.18748081945032, "lng": -0.3705271743228811},
                    {"lat": 49.18672325114213, "lng": -0.37134275747315654},
                ],
                "additionalData": {
                    "mode_plantation": "plantation",
                    "type_haie": "mixte",
                    "vieil_arbre": True,
                    "proximite_mare": False,
                    "sur_parcelle_pac": True,
                    "sur_talus": True,
                    "essences_non_bocageres": False,
                    "recemment_plantee": False,
                    "sous_ligne_electrique": False,
                },
            },
        ]
    )
    return hedge_data


def test_hedge_species_are_filtered_by_geography(
    aisne_map, calvados_map, aisne_hedge_data, calvados_hedge_data  # noqa
):
    aisne_species = SpeciesHabitatFactory(map=aisne_map).species
    aisne_map.zones.update(species_taxrefs=aisne_species.cd_noms)

    calvados_species = SpeciesHabitatFactory(map=calvados_map).species
    calvados_map.zones.update(species_taxrefs=calvados_species.cd_noms)

    hedge = aisne_hedge_data.hedges()[0]
    assert set(Species.hru.for_hedges([hedge])) == set([aisne_species])

    hedge = calvados_hedge_data.hedges()[0]
    assert set(Species.hru.for_hedges([hedge])) == set([calvados_species])


def test_zone_filters_are_not_mixed():  # noqa
    acy_limé_map = MapFactory(map_type="species", zones=None)
    ZoneFactory(
        map=acy_limé_map, geometry=MultiPolygon([acy_polygon]), species_taxrefs=[1]
    )
    ZoneFactory(
        map=acy_limé_map, geometry=MultiPolygon([limé_polygon]), species_taxrefs=[2]
    )
    hypolais = SpeciesFactory(common_name="Hypolaïs ictérine", cd_noms=[1])
    SpeciesHabitatFactory(
        map=acy_limé_map,
        species=hypolais,
        hedge_types=["mixte"],
    )
    huppe = SpeciesFactory(common_name="Huppe fasciée", cd_noms=[2])
    SpeciesHabitatFactory(
        map=acy_limé_map,
        species=huppe,
        hedge_types=["mixte"],
    )
    acy_limé_hedges = HedgeDataFactory(
        data=[
            # Hedge in limé
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.323565543884314, "lng": 3.543156223144537},
                    {"lat": 49.32032072635238, "lng": 3.556141575691475},
                ],
                "additionalData": {
                    "interchamp": True,
                    "type_haie": "mixte",
                    "vieil_arbre": True,
                    "proximite_mare": True,
                    "mode_destruction": "arrachage",
                    "sur_parcelle_pac": True,
                    "connexion_boisement": True,
                    "ripisylve": True,
                },
            },
            # Hedge in Asy
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 49.35080401731072, "lng": 3.410785365407426},
                    {"lat": 49.35021667499731, "lng": 3.4120515874961255},
                ],
                "additionalData": {
                    "interchamp": True,
                    "type_haie": "mixte",
                    "vieil_arbre": True,
                    "proximite_mare": True,
                    "mode_destruction": "arrachage",
                    "sur_parcelle_pac": True,
                    "connexion_boisement": True,
                    "ripisylve": True,
                },
            },
        ]
    )
    species = acy_limé_hedges.get_all_species_hru()
    assert set(species) == set([huppe, hypolais])

    # The second hedge in Acy should not return the Hypolaïs Ictérine anymore
    acy_limé_hedges.data[1]["additionalData"]["type_haie"] = "degradee"
    acy_limé_hedges.save()
    species = acy_limé_hedges.get_all_species_hru()
    assert set(species) == set([huppe])

    acy_limé_hedges.data[1]["additionalData"]["type_haie"] = "mixte"
    acy_limé_hedges.data[0]["additionalData"]["type_haie"] = "degradee"
    acy_limé_hedges.save()
    species = acy_limé_hedges.get_all_species_hru()
    assert set(species) == set([hypolais])


def test_hedge_data_species_are_filtered_by_geography(
    aisne_map, calvados_map, aisne_hedge_data, calvados_hedge_data  # noqa
):
    aisne_species = SpeciesHabitatFactory(map=aisne_map).species
    aisne_map.zones.update(species_taxrefs=aisne_species.cd_noms)

    calvados_species = SpeciesHabitatFactory(map=calvados_map).species
    calvados_map.zones.update(species_taxrefs=calvados_species.cd_noms)

    assert set(aisne_hedge_data.get_all_species_hru()) == set([aisne_species])
    assert set(calvados_hedge_data.get_all_species_hru()) == set([calvados_species])

    aisne_map.zones.all().update(species_taxrefs=[])
    calvados_map.zones.all().update(species_taxrefs=[])

    assert set(aisne_hedge_data.get_all_species_hru()) == set()
    assert set(calvados_hedge_data.get_all_species_hru()) == set()


def test_species_are_filtered_by_hedge_type():
    s1 = SpeciesHabitatFactory(hedge_types=["degradee"]).species
    s2 = SpeciesHabitatFactory(hedge_types=["degradee"]).species
    s3 = SpeciesHabitatFactory(hedge_types=["arbustive"]).species
    hedge = HedgeFactory(additionalData__type_haie="degradee")
    hedges = HedgeDataFactory(hedges=[hedge])

    hedges_species = hedges.get_all_species_hru()
    assert s1 in hedges_species
    assert s2 in hedges_species
    assert s3 not in hedges_species

    hedge = HedgeFactory(
        additionalData__type_haie="arbustive", additionalData__recemment_plantee=False
    )
    hedges = HedgeDataFactory(hedges=[hedge])
    hedges_species = hedges.get_all_species_hru()
    assert s1 not in hedges_species
    assert s2 not in hedges_species
    assert s3 in hedges_species

    # recently planted hedge are considered as "degradee"
    hedge = HedgeFactory(
        additionalData__recemment_plantee=True, additionalData__type_haie="arbustive"
    )
    hedges = HedgeDataFactory(hedges=[hedge])

    hedges_species = hedges.get_all_species_hru()
    assert s1 in hedges_species
    assert s2 in hedges_species
    assert s3 not in hedges_species


def test_hedges_has_centroid_and_department():
    """Test hedges centroid and departement"""
    DepartmentFactory(
        department=34,
        geometry=herault_multipolygon,
    )
    hedge = HedgeDataFactory()
    centroid_to_remove = hedge.get_centroid_to_remove()
    centroid_computed = centroid(hedge.hedges_to_remove()[0].geometry)

    assert centroid_to_remove == centroid_computed
    department = hedge.get_department()

    assert department == "34"


def test_species_are_filtered_by_hedge_features():
    s1 = SpeciesHabitatFactory(
        hedge_properties=["proximite_mare", "vieil_arbre"]
    ).species
    s2 = SpeciesHabitatFactory(hedge_properties=["proximite_mare"]).species
    s3 = SpeciesHabitatFactory(hedge_properties=["vieil_arbre"]).species
    s4 = SpeciesHabitatFactory(hedge_properties=[]).species

    hedge = HedgeFactory(
        additionalData__proximite_mare=False, additionalData__vieil_arbre=False
    )
    hedge_species = Species.hru.for_hedges([hedge])
    assert set(hedge_species) == set([s4])

    hedge = HedgeFactory(
        additionalData__proximite_mare=True, additionalData__vieil_arbre=False
    )
    hedge_species = Species.hru.for_hedges([hedge])
    assert set(hedge_species) == set([s2, s4])

    hedge = HedgeFactory(
        additionalData__proximite_mare=False, additionalData__vieil_arbre=True
    )
    hedge_species = Species.hru.for_hedges([hedge])
    assert set(hedge_species) == set([s3, s4])

    hedge = HedgeFactory(
        additionalData__proximite_mare=True, additionalData__vieil_arbre=True
    )
    hedge_species = Species.hru.for_hedges([hedge])
    assert set(hedge_species) == set([s1, s2, s3, s4])


def test_multiple_hedges_combine_their_species():
    _ = SpeciesHabitatFactory(
        hedge_properties=["proximite_mare", "vieil_arbre"]
    ).species
    s2 = SpeciesHabitatFactory(hedge_properties=["proximite_mare"]).species
    s3 = SpeciesHabitatFactory(hedge_properties=["vieil_arbre"]).species
    s4 = SpeciesHabitatFactory(hedge_properties=[]).species

    hedge1 = HedgeFactory(
        additionalData__proximite_mare=True, additionalData__vieil_arbre=False
    )
    hedge_species = Species.hru.for_hedges([hedge1])
    assert set(hedge_species) == set([s2, s4])

    hedge2 = HedgeFactory(
        additionalData__proximite_mare=False, additionalData__vieil_arbre=True
    )
    hedge_species = Species.hru.for_hedges([hedge2])
    assert set(hedge_species) == set([s3, s4])

    hedges = HedgeDataFactory(hedges=[hedge1, hedge2])
    all_species = hedges.get_all_species_hru()
    assert set(all_species) == set([s2, s3, s4])


def test_hru_no_duplicates_from_multiple_habitats():
    """A species linked to two matching SpeciesHabitats should appear only once."""
    species = SpeciesFactory()
    map1 = MapFactory(map_type="species", zones__species_taxrefs=species.cd_noms)
    map2 = MapFactory(map_type="species", zones__species_taxrefs=species.cd_noms)
    SpeciesHabitatFactory(species=species, map=map1)
    SpeciesHabitatFactory(species=species, map=map2)

    hedge = HedgeFactory()
    result = list(Species.hru.for_hedges([hedge]))
    assert result.count(species) == 1


def test_hedge_to_plant_pac_depends_on_plantation_mode(calvados_hedge_data):
    # mode_plantation is "plantation", hedges is taken into account for pac min length
    hedges = calvados_hedge_data.hedges_to_plant_pac()
    assert len(hedges) == 1

    # hedges with other plantation modes are excluded
    calvados_hedge_data.data[-1]["additionalData"]["mode_plantation"] = "renforcement"
    hedges = calvados_hedge_data.hedges_to_plant_pac()
    assert len(hedges) == 0

    # We ignore the property altogether if it's not set
    del calvados_hedge_data.data[-1]["additionalData"]["mode_plantation"]
    hedges = calvados_hedge_data.hedges_to_plant_pac()
    assert len(hedges) == 1


class TestHedgeList:
    """Test the HedgeList utility class."""

    def test_hedge_list_constructor_with_label(self):
        hedge1 = HedgeFactory(id="A1")
        hedge2 = HedgeFactory(id="A2")
        hedge_list = HedgeList([hedge1, hedge2], label="test_label")

        assert len(hedge_list) == 2
        assert hedge_list.label == "test_label"

    def test_hedge_list_constructor_without_label(self):
        hedge1 = HedgeFactory(id="A1")
        hedge_list = HedgeList([hedge1])

        assert len(hedge_list) == 1
        assert hedge_list.label is None

    def test_names_property(self):
        hedge1 = HedgeFactory(id="A1")
        hedge2 = HedgeFactory(id="B2")
        hedge3 = HedgeFactory(id="C3")
        hedge_list = HedgeList([hedge1, hedge2, hedge3])

        assert hedge_list.names == "A1, B2, C3"

    def test_names_property_empty_list(self):
        hedge_list = HedgeList([])
        assert hedge_list.names == ""

    def test_length_property(self):
        hedge1 = HedgeFactory(length=100.0)
        hedge2 = HedgeFactory(length=200.0)
        hedge_list = HedgeList([hedge1, hedge2])

        # Hedge factory length computing is quite rough
        # So we have to use approx with a good tolerance to make the test pass
        assert hedge_list.length == pytest.approx(300.0, rel=1e-3)

    def test_length_property_empty_list(self):
        hedge_list = HedgeList([])
        assert hedge_list.length == 0

    def test_to_plant_filters_correctly(self):
        hedge_to_plant = HedgeFactory(id="P1", type="TO_PLANT")
        hedge_to_remove = HedgeFactory(id="D1", type="TO_REMOVE")
        hedge_list = HedgeList([hedge_to_plant, hedge_to_remove])

        result = hedge_list.to_plant()

        assert isinstance(result, HedgeList)
        assert len(result) == 1
        assert result[0].id == "P1"

    def test_to_remove_filters_correctly(self):
        hedge_to_plant = HedgeFactory(id="P1", type="TO_PLANT")
        hedge_to_remove = HedgeFactory(id="D1", type="TO_REMOVE")
        hedge_list = HedgeList([hedge_to_plant, hedge_to_remove])

        result = hedge_list.to_remove()

        assert isinstance(result, HedgeList)
        assert len(result) == 1
        assert result[0].id == "D1"

    def test_pac_filters_hedges_on_pac_excluding_alignement(self):
        hedge_pac_degradee = HedgeFactory(
            id="D1",
            additionalData__sur_parcelle_pac=True,
            additionalData__type_haie="degradee",
        )
        hedge_pac_alignement = HedgeFactory(
            id="D2",
            additionalData__sur_parcelle_pac=True,
            additionalData__type_haie="alignement",
        )
        hedge_not_pac = HedgeFactory(
            id="D3",
            additionalData__sur_parcelle_pac=False,
            additionalData__type_haie="mixte",
        )
        hedge_list = HedgeList(
            [hedge_pac_degradee, hedge_pac_alignement, hedge_not_pac]
        )

        result = hedge_list.pac()

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_mixte_filter(self):
        hedge_mixte = HedgeFactory(id="D1", additionalData__type_haie="mixte")
        hedge_other = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge_mixte, hedge_other])

        result = hedge_list.mixte()

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_arbustive_filter(self):
        hedge_arbustive = HedgeFactory(id="D1", additionalData__type_haie="arbustive")
        hedge_other = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge_arbustive, hedge_other])

        result = hedge_list.arbustive()

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_buissonnante_filter(self):
        hedge_buissonnante = HedgeFactory(
            id="D1", additionalData__type_haie="buissonnante"
        )
        hedge_other = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge_buissonnante, hedge_other])

        result = hedge_list.buissonnante()

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_degradee_filter(self):
        hedge_degradee = HedgeFactory(id="D1", additionalData__type_haie="degradee")
        hedge_other = HedgeFactory(id="D2", additionalData__type_haie="mixte")
        hedge_list = HedgeList([hedge_degradee, hedge_other])

        result = hedge_list.degradee()

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_alignement_filter(self):
        hedge_alignement = HedgeFactory(id="D1", additionalData__type_haie="alignement")
        hedge_other = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge_alignement, hedge_other])

        result = hedge_list.alignement()

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_n_alignement_excludes_alignement(self):
        hedge_alignement = HedgeFactory(id="D1", additionalData__type_haie="alignement")
        hedge_degradee = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_mixte = HedgeFactory(id="D3", additionalData__type_haie="mixte")
        hedge_list = HedgeList([hedge_alignement, hedge_degradee, hedge_mixte])

        result = hedge_list.n_alignement()

        assert len(result) == 2
        assert {h.id for h in result} == {"D2", "D3"}

    def test_filter_with_custom_function(self):
        hedge1 = HedgeFactory(id="D1", additionalData__vieil_arbre=True)
        hedge2 = HedgeFactory(id="D2", additionalData__vieil_arbre=False)
        hedge3 = HedgeFactory(id="D3", additionalData__vieil_arbre=True)
        hedge_list = HedgeList([hedge1, hedge2, hedge3])

        result = hedge_list.filter(lambda h: h.vieil_arbre)

        assert len(result) == 2
        assert {h.id for h in result} == {"D1", "D3"}

    def test_type_filter_with_valid_type(self):
        hedge_mixte = HedgeFactory(id="D1", additionalData__type_haie="mixte")
        hedge_degradee = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge_mixte, hedge_degradee])

        result = hedge_list.type("mixte")

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_type_filter_with_negation(self):
        hedge_mixte = HedgeFactory(id="D1", additionalData__type_haie="mixte")
        hedge_degradee = HedgeFactory(id="D2", additionalData__type_haie="degradee")
        hedge_arbustive = HedgeFactory(id="D3", additionalData__type_haie="arbustive")
        hedge_list = HedgeList([hedge_mixte, hedge_degradee, hedge_arbustive])

        result = hedge_list.type("!mixte")

        assert len(result) == 2
        assert {h.id for h in result} == {"D2", "D3"}

    def test_type_filter_with_invalid_type_raises_error(self):
        hedge = HedgeFactory(id="D1")
        hedge_list = HedgeList([hedge])

        with pytest.raises(ValueError) as exc_info:
            hedge_list.type("invalid_type")

        assert "hedge_type must be in" in str(exc_info.value)

    def test_type_filter_with_invalid_negated_type_raises_error(self):
        hedge = HedgeFactory(id="D1")
        hedge_list = HedgeList([hedge])

        with pytest.raises(ValueError) as exc_info:
            hedge_list.type("!invalid_type")

        assert "hedge_type must be in" in str(exc_info.value)

    def test_prop_filter_includes_hedges_with_property_true(self):
        hedge_with_prop = HedgeFactory(id="D1", additionalData__proximite_mare=True)
        hedge_without_prop = HedgeFactory(id="D2", additionalData__proximite_mare=False)
        hedge_list = HedgeList([hedge_with_prop, hedge_without_prop])

        result = hedge_list.prop("proximite_mare")

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_prop_filter_includes_hedges_without_property_defined(self):
        hedge_with_prop = HedgeFactory(id="D1", additionalData__proximite_mare=True)
        hedge_without_definition = HedgeFactory(id="D2")
        # Remove the property from additionalData
        del hedge_without_definition.additionalData["proximite_mare"]
        hedge_list = HedgeList([hedge_with_prop, hedge_without_definition])

        result = hedge_list.prop("proximite_mare")

        assert len(result) == 2
        assert {h.id for h in result} == {"D1", "D2"}

    def test_prop_filter_with_negation(self):
        hedge_with_prop = HedgeFactory(id="D1", additionalData__proximite_mare=True)
        hedge_without_prop = HedgeFactory(id="D2", additionalData__proximite_mare=False)
        hedge_list = HedgeList([hedge_with_prop, hedge_without_prop])

        result = hedge_list.prop("!proximite_mare")

        assert len(result) == 1
        assert result[0].id == "D2"

    def test_prop_filter_negation_includes_undefined_properties(self):
        hedge_with_prop = HedgeFactory(id="D1", additionalData__proximite_mare=True)
        hedge_without_definition = HedgeFactory(id="D2")
        del hedge_without_definition.additionalData["proximite_mare"]
        hedge_list = HedgeList([hedge_with_prop, hedge_without_definition])

        result = hedge_list.prop("!proximite_mare")

        assert len(result) == 1
        assert result[0].id == "D2"

    def test_chaining_filters(self):
        hedge1 = HedgeFactory(
            id="D1",
            type="TO_REMOVE",
            additionalData__type_haie="mixte",
            additionalData__vieil_arbre=True,
        )
        hedge2 = HedgeFactory(
            id="D2",
            type="TO_REMOVE",
            additionalData__type_haie="mixte",
            additionalData__vieil_arbre=False,
        )
        hedge3 = HedgeFactory(
            id="P1",
            type="TO_PLANT",
            additionalData__type_haie="mixte",
            additionalData__vieil_arbre=True,
        )
        hedge4 = HedgeFactory(
            id="D3",
            type="TO_REMOVE",
            additionalData__type_haie="degradee",
            additionalData__vieil_arbre=True,
        )
        hedge_list = HedgeList([hedge1, hedge2, hedge3, hedge4])

        result = hedge_list.to_remove().type("mixte").prop("vieil_arbre")

        assert len(result) == 1
        assert result[0].id == "D1"

    def test_chaining_preserves_hedge_list_type(self):
        hedge = HedgeFactory(id="D1", type="TO_REMOVE")
        hedge_list = HedgeList([hedge])

        result = hedge_list.to_remove().to_remove()

        assert isinstance(result, HedgeList)

    def test_empty_list_operations(self):
        hedge_list = HedgeList([])

        assert len(hedge_list.to_plant()) == 0
        assert len(hedge_list.to_remove()) == 0
        assert len(hedge_list.pac()) == 0
        assert len(hedge_list.mixte()) == 0
        assert len(hedge_list.type("mixte")) == 0
        assert len(hedge_list.prop("vieil_arbre")) == 0

    def test_ru_includes_non_alignement_without_exclusion_props(self):
        hedge = HedgeFactory(id="D1", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.ru()) == 1

    def test_ru_excludes_alignement(self):
        hedge = HedgeFactory(id="D1", additionalData__type_haie="alignement")
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.ru()) == 0

    def test_ru_excludes_bord_batiment(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="degradee",
            additionalData__bord_batiment=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.ru()) == 0

    def test_ru_excludes_parc_jardin(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="degradee",
            additionalData__parc_jardin=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.ru()) == 0

    def test_ru_excludes_place_publique(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="degradee",
            additionalData__place_publique=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.ru()) == 0

    def test_l350_3_includes_alignement_with_bord_voie(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="alignement",
            additionalData__bord_voie=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.l350_3()) == 1

    def test_l350_3_excludes_non_alignement(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="degradee",
            additionalData__bord_voie=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.l350_3()) == 0

    def test_l350_3_excludes_alignement_without_bord_voie(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="alignement",
            additionalData__bord_voie=False,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.l350_3()) == 0

    def test_hru_includes_non_alignement_excluded_from_ru(self):
        # Non-alignement with bord_batiment=True: not in ru, not in l350_3
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="degradee",
            additionalData__bord_batiment=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.hru()) == 1

    def test_hru_includes_alignement_without_bord_voie(self):
        # Alignement with bord_voie=False: not in ru (alignement), not in l350_3 (no bord_voie)
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="alignement",
            additionalData__bord_voie=False,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.hru()) == 1

    def test_hru_excludes_ru_hedges(self):
        hedge = HedgeFactory(id="D1", additionalData__type_haie="degradee")
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.hru()) == 0

    def test_hru_excludes_l350_3_hedges(self):
        hedge = HedgeFactory(
            id="D1",
            additionalData__type_haie="alignement",
            additionalData__bord_voie=True,
        )
        hedge_list = HedgeList([hedge])

        assert len(hedge_list.hru()) == 0

    def test_ru_l350_3_hru_are_a_partition(self):
        hedge_ru = HedgeFactory(id="D1", additionalData__type_haie="degradee")
        hedge_l350_3 = HedgeFactory(
            id="D2",
            additionalData__type_haie="alignement",
            additionalData__bord_voie=True,
        )
        hedge_hru_bord_batiment = HedgeFactory(
            id="D3",
            additionalData__type_haie="mixte",
            additionalData__bord_batiment=True,
        )
        hedge_hru_alignement = HedgeFactory(
            id="D4",
            additionalData__type_haie="alignement",
            additionalData__bord_voie=False,
        )
        hedge_list = HedgeList(
            [hedge_ru, hedge_l350_3, hedge_hru_bord_batiment, hedge_hru_alignement]
        )

        ru = hedge_list.ru()
        l350_3 = hedge_list.l350_3()
        hru = hedge_list.hru()

        assert {h.id for h in ru} == {"D1"}
        assert {h.id for h in l350_3} == {"D2"}
        assert {h.id for h in hru} == {"D3", "D4"}
        # Full partition: every hedge belongs to exactly one group
        assert len(ru) + len(l350_3) + len(hru) == len(hedge_list)


MOCK_DENSITY_CENTROID_200 = {
    "density": 42.0,
    "artifacts": {"length": 1000, "area_ha": 23.8, "truncated_circle": None},
}

MOCK_DENSITY_CENTROID_5000 = {
    "density": 55.0,
    "artifacts": {"length": 50000, "area_ha": 909.0, "truncated_circle": None},
}

MOCK_DENSITY_LINES_400 = {
    "density": 60.0,
    "artifacts": {
        "length": 3000,
        "area_ha": 50.0,
        "buffer_zone": None,
        "truncated_buffer_zone": None,
    },
}

CENTROID_PATCH = (
    "envergo.hedges.models.HedgeData.compute_density_around_points_with_artifacts"
)
LINES_PATCH = (
    "envergo.hedges.models.HedgeData.compute_density_around_lines_with_artifacts"
)


class TestDensityLazyComputation:
    """Verify that each density type is computed independently on demand.

    The two computation methods (centroid-based and line-buffer) are expensive.
    Evaluators that only need one type should never trigger the other.
    """

    def test_density_around_lines_does_not_trigger_centroid_computation(self):
        """Accessing density_around_lines must not compute centroid density."""
        hedge_data = HedgeDataFactory()
        assert hedge_data._density is None

        with (
            patch(CENTROID_PATCH) as mock_centroid,
            patch(LINES_PATCH, return_value=MOCK_DENSITY_LINES_400) as mock_lines,
        ):
            result = hedge_data.density_around_lines

        mock_lines.assert_called_once()
        mock_centroid.assert_not_called()
        assert result["density_400"] == 60.0
        assert "around_centroid" not in hedge_data._density

    def test_density_around_centroid_does_not_trigger_lines_computation(self):
        """Accessing density_around_centroid must not compute line-buffer density."""
        hedge_data = HedgeDataFactory()
        assert hedge_data._density is None

        centroid_return = (
            MOCK_DENSITY_CENTROID_200,
            MOCK_DENSITY_CENTROID_5000,
            None,
        )
        with (
            patch(CENTROID_PATCH, return_value=centroid_return) as mock_centroid,
            patch(LINES_PATCH) as mock_lines,
        ):
            result = hedge_data.density_around_centroid

        mock_centroid.assert_called_once()
        mock_lines.assert_not_called()
        assert result["density_5000"] == 55.0
        assert "around_lines" not in hedge_data._density

    def test_density_properties_compute_incrementally(self):
        """Accessing both properties computes each type exactly once."""
        hedge_data = HedgeDataFactory()

        centroid_return = (
            MOCK_DENSITY_CENTROID_200,
            MOCK_DENSITY_CENTROID_5000,
            None,
        )
        with (
            patch(CENTROID_PATCH, return_value=centroid_return) as mock_centroid,
            patch(LINES_PATCH, return_value=MOCK_DENSITY_LINES_400) as mock_lines,
        ):
            hedge_data.density_around_lines
            hedge_data.density_around_centroid

        mock_lines.assert_called_once()
        mock_centroid.assert_called_once()
        assert "around_lines" in hedge_data._density
        assert "around_centroid" in hedge_data._density

    def test_density_uses_cache(self):
        """Second access to the same property must not recompute."""
        hedge_data = HedgeDataFactory()

        with patch(LINES_PATCH, return_value=MOCK_DENSITY_LINES_400) as mock_lines:
            hedge_data.density_around_lines
            hedge_data.density_around_lines

        mock_lines.assert_called_once()

    def test_density_property_raises_error(self):
        """The legacy density property must raise to prevent accidental use."""
        hedge_data = HedgeDataFactory()

        with pytest.raises(AttributeError, match="density_around_centroid"):
            hedge_data.density


class TestSpeciesModelFields:
    """Phase 1: verify new fields on Species and SpeciesHabitat."""

    def test_species_has_cd_ref_field(self):
        species = SpeciesFactory(cd_ref=42)
        species.refresh_from_db()
        assert species.cd_ref == 42

    def test_species_cd_ref_is_unique(self):
        SpeciesFactory(cd_ref=99)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SpeciesFactory(cd_ref=99)

    def test_species_cd_ref_is_nullable(self):
        species = SpeciesFactory(cd_ref=None)
        species.refresh_from_db()
        assert species.cd_ref is None

    def test_species_has_group_field(self):
        species = SpeciesFactory(group="Mammifères")
        species.refresh_from_db()
        assert species.group == "Mammifères"

    def test_species_adhoc_group_is_optional(self):
        """The ad-hoc group field should accept blank values for new species."""
        species = SpeciesFactory(adhoc_group="")
        species.refresh_from_db()
        assert species.adhoc_group == ""

    def test_species_level_of_concern_is_optional(self):
        """Global level_of_concern can be blank for species created from CD_REF only."""
        species = SpeciesFactory(level_of_concern="")
        species.refresh_from_db()
        assert species.level_of_concern == ""

    def test_species_habitat_has_level_of_concern(self):
        sm = SpeciesHabitatFactory(level_of_concern="fort")
        sm.refresh_from_db()
        assert sm.level_of_concern == "fort"

    def test_species_habitat_level_of_concern_is_nullable(self):
        """Legacy SpeciesHabitats can have null level_of_concern."""
        sm = SpeciesHabitatFactory(level_of_concern=None)
        sm.refresh_from_db()
        assert sm.level_of_concern is None

    def test_levels_of_concern_includes_non_documente(self):
        from envergo.hedges.models import LEVELS_OF_CONCERN

        values = [v for v, _ in LEVELS_OF_CONCERN]
        assert "non_documente" in values


class TestRuSpeciesQuerying:
    """Phase 5: RU species querying with 400m buffer and observed/majeur filtering."""

    # The test hedge runs roughly from lat 49.3508 to 49.3502 at lng 3.411
    HEDGE_LAT = 49.3505

    def _make_zone_near_hedge(self, map_obj, distance_m, species_taxrefs=None):
        """Create a small zone at approximately `distance_m` north of the test hedge.

        One degree of latitude is ~111 km at this latitude.
        """
        offset_deg = distance_m / 111_000.0
        base_lat = self.HEDGE_LAT + offset_deg
        size = 0.001
        poly = Polygon(
            [
                (3.410, base_lat),
                (3.420, base_lat),
                (3.420, base_lat + size),
                (3.410, base_lat + size),
                (3.410, base_lat),
            ]
        )
        return ZoneFactory(
            map=map_obj,
            geometry=MultiPolygon([poly]),
            species_taxrefs=species_taxrefs or [],
        )

    def _make_hedge_in_aisne(self, hedge_type="mixte"):
        """Create a hedge in the Aisne, near the test zone origin."""
        return HedgeFactory(
            latLngs=[
                {"lat": 49.35080401731072, "lng": 3.410785365407426},
                {"lat": 49.35021667499731, "lng": 3.4120515874961255},
            ],
            additionalData={
                "type_haie": hedge_type,
                "vieil_arbre": True,
                "proximite_mare": True,
                "mode_destruction": "arrachage",
                "sur_parcelle_pac": True,
                "ripisylve": False,
                "connexion_boisement": False,
            },
        )

    def test_ru_species_within_400m_buffer(self):
        """Species in a zone within 400m of the hedge are returned."""
        species = SpeciesFactory(cd_ref=5001)
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[5001])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="fort",
        )

        hedge = self._make_hedge_in_aisne()
        result = Species.ru.for_hedges([hedge])
        assert species in set(result)

    def test_ru_species_outside_400m_excluded(self):
        """Species in a zone beyond 400m of the hedge are not returned."""
        species = SpeciesFactory(cd_ref=5002)
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 600, species_taxrefs=[5002])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="fort",
        )

        hedge = self._make_hedge_in_aisne()
        result = Species.ru.for_hedges([hedge])
        assert species not in set(result)

    def test_ru_majeur_observed_included(self):
        """Majeur species observed locally (cd_ref in zone) are included."""
        species = SpeciesFactory(cd_ref=5003)
        map_obj = MapFactory(map_type="species", zones=None)
        # Zone within 400m, species IS in species_taxrefs (observed locally)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[5003])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="majeur",
        )

        hedge = self._make_hedge_in_aisne()
        result = Species.ru.for_hedges([hedge])
        assert species in set(result)

    def test_ru_majeur_not_observed_excluded(self):
        """Majeur species NOT observed locally are excluded from the cortège."""
        species = SpeciesFactory(cd_ref=5004)
        map_obj = MapFactory(map_type="species", zones=None)
        # Zone within 400m, but species NOT in species_taxrefs (not observed)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[9999])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="majeur",
        )

        hedge = self._make_hedge_in_aisne()
        result = Species.ru.for_hedges([hedge])
        assert species not in set(result)

    def test_ru_non_majeur_included_even_without_observation(self):
        """Non-majeur species are included regardless of observation status."""
        species = SpeciesFactory(cd_ref=5005)
        map_obj = MapFactory(map_type="species", zones=None)
        # Zone within 400m, species NOT in species_taxrefs
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="fort",
        )

        hedge = self._make_hedge_in_aisne()
        result = Species.ru.for_hedges([hedge])
        assert species in set(result)

    def test_ru_species_annotated_observed_locally(self):
        """Species should be annotated with observed_locally boolean."""
        observed = SpeciesFactory(cd_ref=5006)
        not_observed = SpeciesFactory(cd_ref=5007)
        map_obj = MapFactory(map_type="species", zones=None)
        # Zone lists only cd_ref=5006
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[5006])
        SpeciesHabitatFactory(
            species=observed,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="fort",
        )
        SpeciesHabitatFactory(
            species=not_observed,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="moyen",
        )

        hedge = self._make_hedge_in_aisne()
        result = list(Species.ru.for_hedges([hedge]))

        observed_result = next(s for s in result if s.cd_ref == 5006)
        not_observed_result = next(s for s in result if s.cd_ref == 5007)
        assert observed_result.observed_locally is True
        assert not_observed_result.observed_locally is False

    def test_ru_species_sorted_by_level_descending(self):
        """Species should be sorted by level_of_concern descending."""
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[])

        faible = SpeciesFactory(cd_ref=6001, common_name="AA Faible")
        fort = SpeciesFactory(cd_ref=6002, common_name="AA Fort")
        majeur_observed = SpeciesFactory(cd_ref=6003, common_name="AA Majeur")
        # Majeur is observed so it's included
        self._make_zone_near_hedge(map_obj, 100, species_taxrefs=[6003])
        for sp, level in [
            (faible, "faible"),
            (fort, "fort"),
            (majeur_observed, "majeur"),
        ]:
            SpeciesHabitatFactory(
                species=sp,
                map=map_obj,
                hedge_types=["mixte"],
                level_of_concern=level,
            )

        hedge = self._make_hedge_in_aisne()
        hedges = HedgeDataFactory(hedges=[hedge])
        result = list(hedges.get_all_species())

        levels = [s.local_level_of_concern for s in result]
        assert levels == ["majeur", "fort", "faible"]

    def test_ru_null_level_of_concern_treated_as_non_majeur(self):
        """Species with NULL level_of_concern on SpeciesHabitat are included."""
        species = SpeciesFactory(cd_ref=7001)
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern=None,
        )

        hedge = self._make_hedge_in_aisne()
        result = list(Species.ru.for_hedges([hedge]))
        assert species in result

    def test_ru_null_cd_ref_observed_locally_false(self):
        """Species with NULL cd_ref are never considered observed locally."""
        species = SpeciesFactory(cd_ref=None)
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[])
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["mixte"],
            level_of_concern="fort",
        )

        hedge = self._make_hedge_in_aisne()
        result = list(Species.ru.for_hedges([hedge]))
        match = next(s for s in result if s.pk == species.pk)
        assert match.observed_locally is False

    def test_ru_no_duplicates_from_multiple_maps(self):
        """A species in multiple nearby maps should appear exactly once."""
        species = SpeciesFactory(cd_ref=7003)
        map1 = MapFactory(map_type="species", zones=None)
        map2 = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map1, 200, species_taxrefs=[7003])
        self._make_zone_near_hedge(map2, 300, species_taxrefs=[7003])
        SpeciesHabitatFactory(
            species=species,
            map=map1,
            hedge_types=["mixte"],
            level_of_concern="fort",
        )
        SpeciesHabitatFactory(
            species=species,
            map=map2,
            hedge_types=["mixte"],
            level_of_concern="moyen",
        )

        hedge = self._make_hedge_in_aisne()
        result = list(Species.ru.for_hedges([hedge]))
        assert result.count(species) == 1

    def test_ru_ecological_properties_exclusion(self):
        """Species requiring ecological properties the hedge lacks are excluded."""
        needs_ripisylve = SpeciesFactory(cd_ref=7004)
        no_requirements = SpeciesFactory(cd_ref=7005)
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[])
        SpeciesHabitatFactory(
            species=needs_ripisylve,
            map=map_obj,
            hedge_types=["mixte"],
            hedge_properties=["ripisylve"],
            level_of_concern="fort",
        )
        SpeciesHabitatFactory(
            species=no_requirements,
            map=map_obj,
            hedge_types=["mixte"],
            hedge_properties=[],
            level_of_concern="fort",
        )

        # Hedge explicitly lacks ripisylve
        hedge = self._make_hedge_in_aisne()
        result = set(Species.ru.for_hedges([hedge]))
        assert needs_ripisylve not in result
        assert no_requirements in result

    def test_ru_level_subquery_picks_highest_level(self):
        """When a species appears in two maps, the highest level is annotated."""
        species = SpeciesFactory(cd_ref=7006)
        map_low = MapFactory(map_type="species", zones=None)
        map_high = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_low, 200, species_taxrefs=[])
        self._make_zone_near_hedge(map_high, 300, species_taxrefs=[])
        SpeciesHabitatFactory(
            species=species,
            map=map_low,
            hedge_types=["mixte"],
            level_of_concern="faible",
        )
        SpeciesHabitatFactory(
            species=species,
            map=map_high,
            hedge_types=["mixte"],
            level_of_concern="tres_fort",
        )

        hedge = self._make_hedge_in_aisne()
        result = list(Species.ru.for_hedges([hedge]))
        match = next(s for s in result if s.pk == species.pk)
        assert match.local_level_of_concern == "tres_fort"

    def test_ru_species_not_leaked_across_signatures(self):
        """A species near hedge A must not match hedge B's signature filter.

        Regression test: the RU filter used to compute nearby_map_ids as a
        union across all hedges, so a species whose habitat map was only
        near hedge A could match hedge B's (hedge_type, missing_props)
        filter. With per-signature zone scoping, the species should only
        appear if a hedge of the matching type is within 400m.
        """
        map_obj = MapFactory(map_type="species", zones=None)
        self._make_zone_near_hedge(map_obj, 200, species_taxrefs=[])

        species = SpeciesFactory(cd_ref=8001)
        SpeciesHabitatFactory(
            species=species,
            map=map_obj,
            hedge_types=["degradee"],
            level_of_concern="fort",
        )

        # Hedge A is near the zone but has type "mixte" — wrong signature
        hedge_a = self._make_hedge_in_aisne(hedge_type="mixte")

        # Hedge B is far away but has type "degradee" — right signature
        hedge_b = HedgeFactory(
            latLngs=[
                {"lat": 43.687177, "lng": 3.584794},
                {"lat": 43.687301, "lng": 3.585910},
            ],
            additionalData={
                "type_haie": "degradee",
                "vieil_arbre": False,
                "proximite_mare": False,
                "mode_destruction": "arrachage",
                "sur_parcelle_pac": True,
                "ripisylve": False,
                "connexion_boisement": False,
            },
        )

        result = set(Species.ru.for_hedges([hedge_a, hedge_b]))
        assert species not in result

        # Sanity: a degradee hedge near the zone DOES return the species
        hedge_c = self._make_hedge_in_aisne(hedge_type="degradee")
        result = set(Species.ru.for_hedges([hedge_c]))
        assert species in result
