"""Render HTML documents as PDF files.

Importing this module loads WeasyPrint's native libraries.
"""

from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from django.conf import settings
from weasyprint import HTML
from weasyprint.urls import FatalURLFetchingError, URLFetcher


class StaticFilesFetcher(URLFetcher):
    """Fetch the collected static files only. Any failure stops the rendering."""

    def __init__(self):
        super().__init__(fail_on_errors=True)

    def fetch(self, url, headers=None):
        """Refuse anything but a file in the static folder, then fetch it as usual."""
        parsed_url = urlparse(url)
        if parsed_url.scheme != "file":
            raise ValueError(f"{url} is not a local file.")

        path = Path(url2pathname(parsed_url.path)).resolve()
        static_root = Path(settings.STATIC_ROOT).resolve()
        if not path.is_relative_to(static_root):
            raise ValueError(f"{url} is outside the static files.")

        return super().fetch(url, headers)


def render_pdf(html) -> bytes:
    """Render an HTML document whose resources are collected static files.

    Raises RuntimeError when a resource is missing or outside the static files.
    """
    static_root = f"{settings.STATIC_ROOT}/"
    document = HTML(string=html, base_url=static_root, url_fetcher=StaticFilesFetcher())
    try:
        # PDF/A-2a: the archival format for official acts, with an accessible structure.
        pdf = document.write_pdf(pdf_variant="pdf/a-2a")
    except FatalURLFetchingError as error:
        # It derives from BaseException, which `except Exception` handlers miss.
        raise RuntimeError(str(error)) from error

    return pdf
