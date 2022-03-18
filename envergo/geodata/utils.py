import glob
import logging
import zipfile
from tempfile import TemporaryDirectory

import requests
from django.contrib.gis.utils.layermapping import LayerMapping
from requests.exceptions import ConnectTimeout, JSONDecodeError

from envergo.geodata.models import DepartmentContact, Zone

logger = logging.getLogger(__name__)


class CustomMapping(LayerMapping):
    def __init__(self, *args, **kwargs):
        self.extra_kwargs = kwargs.pop("extra_kwargs")
        super().__init__(*args, **kwargs)

    def feature_kwargs(self, feat):
        kwargs = super().feature_kwargs(feat)
        kwargs.update(self.extra_kwargs)
        return kwargs


def extract_shapefile(map, file):

    logger.info("Creating temporary directory")
    with TemporaryDirectory() as tmpdir:

        logger.info("Extracting map zip file")
        zf = zipfile.ZipFile(file)
        zf.extractall(tmpdir)

        logger.info("Find .shp file path")
        paths = glob.glob(f"{tmpdir}/*shp")  # glop glop !
        shapefile = paths[0]

        logger.info("Instanciating custom LayerMapping")
        mapping = {"geometry": "MULTIPOLYGON"}
        extra = {"map": map}
        lm = CustomMapping(Zone, shapefile, mapping, extra_kwargs=extra)

        logger.info("Calling layer mapping `save`")
        lm.save()


def fetch_department_code(lng, lat):
    """Use the IGN api to find department code from coordinates.

    See https://geoservices.ign.fr/documentation/services/services-beta/geocodage-beta/documentation-du-geocodage#2469
    """
    url = f'https://geocodage.ign.fr/look4/poi/reverse?searchGeom={{"type":"Point","coordinates":[{lng},{lat}]}}&filters[type]=département'

    try:
        res = requests.get(url, timeout=5)
        data = res.json()
        departmentCode = data["features"][1]["properties"]["inseeCode"][0]
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
        departmentContact = DepartmentContact.objects.filter(
            department=departmentCode
        ).first()

        if departmentContact:
            contactData = departmentContact.contact_html
        else:
            logger.warning(f"No contact data for department {departmentCode}")

    return contactData
