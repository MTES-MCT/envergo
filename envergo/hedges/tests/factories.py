import factory
from factory.django import DjangoModelFactory

from envergo.hedges.models import Hedge, HedgeData, Species


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
            "typeHaie": "degradee",
            "surParcellePac": True,
            "proximiteMare": False,
            "vieilArbre": False,
            "proximitePointEau": False,
            "connexionBoisement": False,
        }
    )


class HedgeDataFactory(DjangoModelFactory):
    class Meta:
        model = HedgeData

    data = factory.List([HedgeFactory().toDict()])

    @factory.post_generation
    def hedges(obj, create, extracted, **kwargs):
        obj.data = [hedge.toDict() for hedge in extracted]


class SpeciesFactory(DjangoModelFactory):
    class Meta:
        model = Species

    common_name = factory.Sequence(lambda n: f"Trucmuche {n}")
    scientific_name = factory.Sequence(lambda n: f"Machinchose {n}")
    hedge_types = ["degradee", "buissonnante", "arbustive", "alignement", "mixte"]
    proximite_mare = False
    proximite_point_eau = False
    connexion_boisement = False
    vieil_arbre = False
