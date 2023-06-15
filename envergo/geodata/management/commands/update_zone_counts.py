from django.core.management.base import BaseCommand
from django.db.models import Case, Count, F, OuterRef, Subquery, Value, When

from envergo.geodata.models import STATUSES, Map, Zone


class Command(BaseCommand):
    help = "Mise à jour du champ `imported_zones`."

    def handle(self, *args, **options):
        zone_count = Subquery(
            Zone.objects.filter(map_id=OuterRef("id"))
            .values("map_id")
            .annotate(count=Count("id"))
            .values("count")
        )
        Map.objects.annotate(nb_zones=zone_count).update(
            imported_zones=F("nb_zones"),
            import_status=Case(
                When(nb_zones=F("expected_zones"), then=Value(STATUSES.success)),
                When(nb_zones__gt=0, then=Value(STATUSES.partial_success)),
                default=Value(STATUSES.failure),
            ),
        )
