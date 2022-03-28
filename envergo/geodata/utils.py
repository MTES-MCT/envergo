import glob
import logging
import re
import sys
import zipfile
from tempfile import TemporaryDirectory

import requests
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.utils.layermapping import LayerMapping
from requests.exceptions import ConnectTimeout, JSONDecodeError

from envergo.geodata.models import Department, Zone

logger = logging.getLogger(__name__)


class CeleryDebugStream:
    """A sys.stdout proxy that also updates the celery task states.

    Django's LayerMapping does not offer any hook to update the long running
    import task. It does provides a way to print the task's progress, though,
    by offering a `stream` argument to the `save` method.
    """

    def __init__(self, task, nb_zones):
        self.task = task
        self.nb_zones = nb_zones

    def write(self, msg):

        # Find the number of processed results from progress message
        match = re.search(r"\d+", msg)
        nb_processed = int(match[0])
        progress = int(nb_processed / self.nb_zones * 100)

        # update task statk
        task_msg = f"{nb_processed} zones importées sur {self.nb_zones} ({progress}%)"
        self.task.update_state(state="PROGRESS", meta={"msg": task_msg})

        sys.stdout.write(msg)


class CustomMapping(LayerMapping):
    def __init__(self, *args, **kwargs):
        self.extra_kwargs = kwargs.pop("extra_kwargs")
        super().__init__(*args, **kwargs)

    def feature_kwargs(self, feat):
        kwargs = super().feature_kwargs(feat)
        kwargs.update(self.extra_kwargs)
        return kwargs


def extract_shapefile(map, file, task=None):

    logger.info("Creating temporary directory")
    with TemporaryDirectory() as tmpdir:

        logger.info("Extracting map zip file")
        zf = zipfile.ZipFile(file)
        zf.extractall(tmpdir)

        logger.info("Find .shp file path")
        paths = glob.glob(f"{tmpdir}/*shp")  # glop glop !
        shapefile = paths[0]

        logger.info("Fetching data about the shapefile")
        ds = DataSource(shapefile)
        layer = ds[0]
        nb_zones = len(layer)

        if task:
            debug_stream = CeleryDebugStream(task, nb_zones)
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


def fetch_department_code(lng, lat):
    """Use the IGN api to find department code from coordinates.

    See https://geoservices.ign.fr/documentation/services/services-beta/geocodage-beta/documentation-du-geocodage#2469
    """
    url = f'https://geocodage.ign.fr/look4/poi/reverse?searchGeom={{"type":"Point","coordinates":[{lng},{lat}]}}&filters[type]=département'  # noqa

    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        departmentCode = data["features"][0]["properties"]["inseeCode"][0]
    except (ConnectTimeout, JSONDecodeError, KeyError, IndexError) as err:

        logger.error(
            f"Cannot find department code for {lng},{lat} (url = {url}) (error = {err})"
        )
        departmentCode = None

    return departmentCode


def find_contact_data(lng, lat):
    """Return department contact data for the given coordinates"""

    contactData = ""

    departmentCode = fetch_department_code(lng, lat)
    if departmentCode:
        department = Department.objects.filter(department=departmentCode).first()

        if department:
            contactData = department.contact_html
        else:
            logger.warning(f"No contact data for department {departmentCode}")

    return contactData
