"""Urbanisme haie is declined per hedge category, and each map link is its own.

`geoportail_url` is centered on the evaluator's hedges, so the three category
variants compute three different links for the same project. Evaluators keep
their values out of the shared catalog, and each criterion body is rendered with
the values its own evaluator computed.
"""

import pytest
from django.template import Context
from django.utils.html import escape

from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.templatetags.moulinette import show_criterion_body
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    RegulationFactory,
    RUConfigHaieFactory,
)
from envergo.moulinette.tests.utils import (
    COORDS_BIZOUS_INSIDE,
    make_hedge,
    make_moulinette_haie_data,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def urbanisme_haie_criteria(france_map):  # noqa
    regulation = RegulationFactory(regulation="urbanisme_haie")
    return [
        CriterionFactory(
            title=f"Urbanisme haie - {category}",
            regulation=regulation,
            evaluator=f"envergo.moulinette.regulations.urbanisme_haie.{evaluator}",
            activation_map=france_map,
            activation_mode="department_centroid",
        )
        for category, evaluator in [
            ("hru", "UrbanismeHaieHru"),
            ("ru", "UrbanismeHaieRu"),
            ("l350_3", "UrbanismeHaieL3503"),
        ]
    ]


def shifted_coords(offset):
    """Move a hedge slightly, so each category ends up on its own centroid."""
    return [(lat + offset, lng + offset) for lat, lng in COORDS_BIZOUS_INSIDE]


def build_multi_category_moulinette():
    """A project holding one hedge of each category, each in its own spot."""
    RUConfigHaieFactory()
    moulinette = MoulinetteHaie(
        make_moulinette_haie_data(
            hedge_data=[
                make_hedge(
                    hedge_id="RU", type_haie="mixte", coords=shifted_coords(0.0)
                ),
                make_hedge(
                    hedge_id="AA",
                    type_haie="alignement",
                    bord_voie=True,
                    coords=shifted_coords(0.001),
                ),
                make_hedge(
                    hedge_id="HRU",
                    type_haie="alignement",
                    bord_voie=False,
                    coords=shifted_coords(0.002),
                ),
            ],
            motif="securite",
            reimplantation="replantation",
        )
    )
    assert moulinette.is_valid(), moulinette.form_errors
    return moulinette


@pytest.fixture
def multi_category_moulinette():
    return build_multi_category_moulinette()


def test_each_criterion_carries_its_own_geoportail_url(multi_category_moulinette):
    criteria = list(multi_category_moulinette.urbanisme_haie.criteria.all())
    assert len(criteria) == 3

    urls = [c.get_catalog_data()["geoportail_url"] for c in criteria]
    assert len(set(urls)) == 3, urls


def test_criterion_body_renders_its_own_geoportail_url(multi_category_moulinette):
    """The rendered body shows the link of its own category, not the last one."""

    regulation = multi_category_moulinette.urbanisme_haie
    context = Context({"moulinette": multi_category_moulinette})

    rendered = {}
    for criterion in regulation.criteria.all():
        body = show_criterion_body(context, regulation, criterion)
        rendered[criterion.evaluator.category.name] = body
        own_url = criterion.get_catalog_data()["geoportail_url"]
        assert escape(own_url) in body

    assert len(set(rendered.values())) == 3


def test_evaluators_do_not_write_into_the_shared_catalog(multi_category_moulinette):
    """A per-category value has no meaning for the whole project."""

    assert "geoportail_url" not in multi_category_moulinette.catalog
