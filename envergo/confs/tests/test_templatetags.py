import pytest
from django.template import Context, Template
from django.test import RequestFactory

from envergo.confs.tests.factories import TopBarFactory

pytestmark = pytest.mark.django_db


def test_top_bar_displayed(site):
    """Test top_bar data sent to template."""

    # GIVEN an active top bar
    topbar = TopBarFactory(site=site)
    factory = RequestFactory()
    request = factory.get("")
    request.site = site
    request.session = {}
    # WHEN I want to show top bar in a template
    template_html = "{% load confs %}{% top_bar %}"
    context_data = {"request": request}
    content = Template(template_html).render(Context(context_data))
    # THEN this top bar text is in template
    assert topbar.message_html in content
