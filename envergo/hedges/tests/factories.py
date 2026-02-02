import factory
from factory.django import DjangoModelFactory
from shapely import LineString

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
            "mode_destruction": "autre",
            "type_haie": "degradee",
            "sur_parcelle_pac": True,
            "proximite_mare": False,
            "vieil_arbre": False,
            "proximite_point_eau": False,
            "connexion_boisement": False,
        }
    )

    @factory.post_generation
    def length(obj, create, extracted, **kwargs):
        """Force the hedge to be a specific (although very approximate) length."""
        if extracted:

            # One degree of latitude is approx 111 km
            obj.latLngs[1]["lng"] = obj.latLngs[0]["lng"]
            obj.latLngs[1]["lat"] = obj.latLngs[0]["lat"] + (extracted / 111000.0)
            obj.geometry = LineString(
                [(latLng["lng"], latLng["lat"]) for latLng in obj.latLngs]
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
    map = factory.SubFactory(
        MapFactory,
        zones__species_taxrefs=factory.SelfAttribute("...species.taxref_ids"),
    )
    hedge_types = ["degradee", "buissonnante", "arbustive", "alignement", "mixte"]
    hedge_properties = []
