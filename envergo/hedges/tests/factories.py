from factory.django import DjangoModelFactory

from envergo.hedges.models import HedgeData


class HedgeDataFactory(DjangoModelFactory):
    class Meta:
        model = HedgeData

    data = (
        '[{"id":"D1","latLngs":[{"lat":43.687177253462714,"lng":3.58479488061279},'
        '{"lat":43.687301385409,"lng":3.5859104885342323}],"type":"TO_REMOVE"}]'
    )
