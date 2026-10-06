import io
from pathlib import Path
from unittest.mock import Mock, patch

from envergo.geodata.utils import extract_map

# Stored files must resolve to the real S3 url (s3_url), never the
# browser-facing proxy url.


def make_stored_gpkg(s3_url, path="/var/media/maps/departements.gpkg"):
    """A FieldFile stand-in: only attributes the real class has."""
    archive = Mock(spec=["storage", "name", "path"])
    archive.name = "maps/departements.gpkg"
    archive.storage = Mock(spec=["s3_url"])
    archive.storage.s3_url.return_value = s3_url
    archive.path = path
    return archive


@patch("envergo.geodata.utils.requests.get")
def test_remote_gpkg_yields_a_local_gpkg_copy(mock_get):
    signed_url = (
        "https://s3.fr-par.scw.cloud/bucket/media/maps/departements.gpkg"
        "?X-Amz-Signature=abc"
    )
    mock_get.return_value.raw = io.BytesIO(b"gpkg content")
    archive = make_stored_gpkg(signed_url)
    with extract_map(archive) as map_file:
        assert mock_get.call_args.args == (signed_url,)
        assert map_file.endswith(".gpkg")
        assert Path(map_file).read_bytes() == b"gpkg content"
    assert not Path(map_file).exists()


def test_local_gpkg_yields_the_filesystem_path():
    archive = make_stored_gpkg("/media/maps/departements.gpkg")
    with extract_map(archive) as map_file:
        assert map_file == archive.path
