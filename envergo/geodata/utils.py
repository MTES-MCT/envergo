import glob
import logging
import re
import sys
import zipfile
from contextlib import contextmanager
from tempfile import TemporaryDirectory

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.utils.layermapping import LayerMapping
from django.utils.translation import gettext_lazy as _

from envergo.geodata.models import Zone

logger = logging.getLogger(__name__)


class CeleryDebugStream:
    """A sys.stdout proxy that also updates the celery task states.

    Django's LayerMapping does not offer any hook to update the long running
    import task. It does provides a way to print the task's progress, though,
    by offering a `stream` argument to the `save` method.
    """

    def __init__(self, task, expected_zones):
        self.task = task
        self.expected_zones = expected_zones

    def write(self, msg):

        sys.stdout.write(msg)

        # Find the number of processed results from progress message
        if msg.startswith("Processed"):
            match = re.search(r"\d+", msg)
            nb_saved = int(match[1])
            progress = int(nb_saved / self.expected_zones * 100)

            # update task state
            task_msg = (
                f"{nb_saved} zones importées sur {self.expected_zones} ({progress}%)"
            )
            self.task.update_state(state="PROGRESS", meta={"msg": task_msg})


class CustomMapping(LayerMapping):
    def __init__(self, *args, **kwargs):
        self.extra_kwargs = kwargs.pop("extra_kwargs")
        super().__init__(*args, **kwargs)

    def feature_kwargs(self, feat):
        kwargs = super().feature_kwargs(feat)
        kwargs.update(self.extra_kwargs)
        return kwargs


@contextmanager
def extract_shapefile(archive):
    """Extract a shapefile from a zip archive."""

    with TemporaryDirectory() as tmpdir:
        logger.info("Extracting map zip file")
        zf = zipfile.ZipFile(archive)
        zf.extractall(tmpdir)

        logger.info("Find .shp file path")
        paths = glob.glob(f"{tmpdir}/*shp")  # glop glop !

        try:
            shapefile = paths[0]
        except IndexError:
            raise ValueError(_("No .shp file found in archive"))

        yield shapefile


def count_features(shapefile):
    """Count the number of features from a shapefile."""

    with extract_shapefile(shapefile) as file:
        ds = DataSource(file)
        layer = ds[0]
        nb_zones = len(layer)

    return nb_zones


def process_shapefile(map, file, task=None):

    logger.info("Creating temporary directory")
    with extract_shapefile(file) as shapefile:
        if task:
            debug_stream = CeleryDebugStream(task, map.expected_zones)
        else:
            debug_stream = sys.stdout

        logger.info("Instanciating custom LayerMapping")
        mapping = {"geometry": "MULTIPOLYGON"}
        extra = {"map": map}
        lm = CustomMapping(
            Zone,
            shapefile,
            mapping,
            transaction_mode="autocommit",
            extra_kwargs=extra,
        )

        logger.info("Calling layer mapping `save`")
        lm.save(strict=False, progress=True, stream=debug_stream)
        logger.info("Importing is done")
