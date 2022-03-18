from config.celery_app import app
from envergo.geodata.models import Map
from envergo.geodata.utils import extract_shapefile


@app.task(bind=True)
def process_shapefile_map(task, map_id):
    """Send a Mattermost notification to confirm the evaluation request."""

    map = Map.objects.get(pk=map_id)
    map.zones.all().delete()
    extract_shapefile(map, map.file)
