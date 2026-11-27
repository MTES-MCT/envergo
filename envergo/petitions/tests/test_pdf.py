import pytest
from django.test import override_settings

from envergo.petitions.pdf import StaticFilesFetcher, render_pdf

MISSING_FONT_HTML = """
<style>
  @font-face { font-family: Marianne; src: url("fonts/Marianne-Regular.woff2"); }
  body { font-family: Marianne; }
</style>
<p>Attestation</p>
"""


def test_rendering_fails_on_a_missing_font(tmp_path):
    """A missing font stops the rendering instead of falling back to another one."""
    with override_settings(STATIC_ROOT=str(tmp_path)):
        with pytest.raises(RuntimeError, match="Marianne-Regular.woff2"):
            render_pdf(MISSING_FONT_HTML)


def test_fetcher_refuses_files_outside_the_static_folder(tmp_path):
    """The renderer only reads the collected static files."""
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    static_root = tmp_path / "static"
    static_root.mkdir()

    with override_settings(STATIC_ROOT=str(static_root)):
        with pytest.raises(ValueError, match="outside the static files"):
            StaticFilesFetcher().fetch(outside.as_uri())


def test_fetcher_refuses_web_addresses(tmp_path):
    """The renderer never reaches the network, whatever the address's path."""
    path_inside_static_root = f"{tmp_path}/font.woff2"
    web_url = f"https://example.com{path_inside_static_root}"

    with override_settings(STATIC_ROOT=str(tmp_path)):
        with pytest.raises(ValueError, match="not a local file"):
            StaticFilesFetcher().fetch(web_url)
