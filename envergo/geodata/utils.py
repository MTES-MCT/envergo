import glob
import zipfile
from tempfile import TemporaryDirectory

from django.contrib.gis.utils import LayerMapping

from envergo.geodata.models import Zone


def extract_shapefile(map, file):

    with TemporaryDirectory() as tmpdir:
        zf = zipfile.ZipFile(file)
        zf.extractall(tmpdir)

        paths = glob.glob(f"{tmpdir}/*shp")  # glop glop !
        shapefile = paths[0]
        mapping = {"geometry": "POLYGON"}
        lm = LayerMapping(Zone, shapefile, mapping)
        lm.save(verbose=True)
