from django.core.management.base import BaseCommand
from django.db.models import Count, OuterRef, Subquery

from envergo.geodata.models import Map, Zone


class Command(BaseCommand):
    help = "Mise à jour du champ `imported_zones`."

    def handle(self, *args, **options):
        zone_count = Subquery(
            Zone.objects.filter(map_id=OuterRef("id"))
            .values("map_id")
            .annotate(count=Count("id"))
            .values("count")
        )
        Map.objects.update(imported_zones=zone_count)
