import pytest

from envergo.utils.urls import join_url

BASE = "https://matrix.agent.tchap.gouv.fr"


@pytest.mark.parametrize(
    "base",
    [BASE, f"{BASE}/", f"{BASE}//"],
)
def test_join_url_ignores_base_trailing_slashes(base):
    assert join_url(base, "_matrix", "client") == f"{BASE}/_matrix/client"


@pytest.mark.parametrize(
    "base",
    ["https://example.org/matrix", "https://example.org/matrix/"],
)
def test_join_url_keeps_the_base_path(base):
    assert join_url(base, "_matrix") == "https://example.org/matrix/_matrix"


@pytest.mark.parametrize(
    "segments",
    [
        ("_matrix", "client"),
        ("/_matrix/", "/client/"),
        ("_matrix/", "client"),
        ("_matrix", "", "client"),
    ],
)
def test_join_url_ignores_segment_slashes(segments):
    assert join_url(BASE, *segments) == f"{BASE}/_matrix/client"


def test_join_url_joins_multi_segment_parts_verbatim():
    assert (
        join_url(BASE, "_matrix/client/v3/rooms") == f"{BASE}/_matrix/client/v3/rooms"
    )


def test_join_url_without_segment():
    assert join_url(f"{BASE}/") == BASE
