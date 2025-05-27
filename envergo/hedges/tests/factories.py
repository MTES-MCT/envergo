import factory
from factory.django import DjangoModelFactory

from envergo.geodata.tests.factories import MapFactory
from envergo.hedges.models import Hedge, HedgeData, Species, SpeciesMap


class HedgeFactory(factory.Factory):
    class Meta:
        model = Hedge

    id = factory.sequence(lambda n: f"D{n}")
    type = "TO_REMOVE"
    latLngs = [
        {"lat": 43.687177253462714, "lng": 3.58479488061279},
        {"lat": 43.687301385409, "lng": 3.5859104885342323},
    ]
    additionalData = factory.Dict(
        {
            "position": "autre",
            "mode_destruction": "autre",
            "type_haie": "degradee",
            "sur_parcelle_pac": True,
            "proximite_mare": False,
            "vieil_arbre": False,
            "proximite_point_eau": False,
            "connexion_boisement": False,
        }
    )


class HedgeDataFactory(DjangoModelFactory):
    class Meta:
        model = HedgeData

    data = factory.List([HedgeFactory().toDict()])

    @factory.post_generation
    def hedges(obj, create, extracted, **kwargs):
        if extracted:
            obj.data = [hedge.toDict() for hedge in extracted]


class SpeciesFactory(DjangoModelFactory):
    class Meta:
        model = Species

    common_name = factory.Sequence(lambda n: f"Trucmuche {n}")
    scientific_name = factory.Sequence(lambda n: f"Machinchose {n}")

    @factory.sequence
    def taxref_ids(n):
        return [n]


class SpeciesMapFactory(DjangoModelFactory):
    class Meta:
        model = SpeciesMap

    species = factory.SubFactory(SpeciesFactory)
    map = factory.SubFactory(MapFactory)
    hedge_types = ["degradee", "buissonnante", "arbustive", "alignement", "mixte"]
    hedge_properties = []

    @factory.post_generation
    def post(obj, create, extracted, **kwargs):
        # Make sure that the species are linked to the map polygons
        obj.map.zones.all().update(species_taxrefs=obj.species.taxref_ids)
        obj.map.map_type = "species"
        obj.map.save()
