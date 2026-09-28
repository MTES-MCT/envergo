from unittest.mock import Mock

from envergo.geodata.utils import extract_map

# GDAL fetches .gpkg files over plain HTTP with no session: stored files must
# resolve to the real S3 url (s3_url), never the browser-facing proxy url.


def make_stored_gpkg(s3_url, path="/var/media/maps/departements.gpkg"):
    """A FieldFile stand-in: only attributes the real class has."""
    archive = Mock(spec=["storage", "name", "path"])
    archive.name = "maps/departements.gpkg"
    archive.storage = Mock(spec=["s3_url"])
    archive.storage.s3_url.return_value = s3_url
    archive.path = path
    return archive


def test_remote_gpkg_yields_the_s3_url():
    signed_url = (
        "https://s3.fr-par.scw.cloud/bucket/media/maps/departements.gpkg"
        "?X-Amz-Signature=abc"
    )
    archive = make_stored_gpkg(signed_url)
    with extract_map(archive) as map_file:
        assert map_file == signed_url


def test_local_gpkg_yields_the_filesystem_path():
    archive = make_stored_gpkg("/media/maps/departements.gpkg")
    with extract_map(archive) as map_file:
        assert map_file == archive.path
