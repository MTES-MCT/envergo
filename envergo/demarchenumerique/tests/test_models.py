import pytest
from django.core.exceptions import ValidationError

from envergo.demarchenumerique.models import DemarcheConfig
from envergo.geodata.conftest import bizous_town_center  # noqa: F401
from envergo.geodata.tests.factories import MapFactory
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    HaieRegulationFactory,
    PerimeterFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.django_db


def test_dn_config_has_missing_project_url_id():
    """Check `project_url_id_required_if_demarche_number` constraint"""
    demarche = DemarcheConfig(demarche_numerique_number="123456789")
    with pytest.raises(ValidationError):
        demarche.validate_constraints()


def test_demarche_numerique_has_invalid_pre_fill_config():
    with pytest.raises(ValidationError) as exc_info:
        demarche = DemarcheConfig(
            demarche_numerique_number="123456789",
            pre_fill_config={"foo": "bar"},
        )
        demarche.clean()
    assert exc_info.value.messages == [
        "Cette configuration doit être une liste de champs (ou d'annotations privées) à pré-remplir"
    ]

    with pytest.raises(ValidationError) as exc_info:
        demarche = DemarcheConfig(
            demarche_numerique_number="123456789",
            pre_fill_config=[{"foo": "bar"}],
        )
        demarche.clean()
    assert exc_info.value.messages == [
        "Chaque champ (ou annotation privée) doit contenir au moins l'id côté « Démarche numérique » et la "
        "source de la valeur côté guichet unique de la haie."
    ]

    with pytest.raises(ValidationError) as exc_info:
        demarche = DemarcheConfig(
            demarche_numerique_number="123456789",
            pre_fill_config=[{"id": "123456789", "value": "bar"}],
        )
        demarche.clean()
    assert exc_info.value.messages == [
        "La source de la valeur bar n'est pas valide pour le champ dont l'id est 123456789"
    ]

    with pytest.raises(
        ValidationError,
        match="Le mapping du champ dont l'id est 123456789 doit être un dictionnaire.",
    ):
        demarche = DemarcheConfig(
            demarche_numerique_number="123456789",
            pre_fill_config=[
                {"id": "123456789", "value": "localisation_pac", "mapping": "bar"}
            ],
        )
        demarche.clean()

    demarche = DemarcheConfig(
        demarche_numerique_number="123456789",
        pre_fill_config=[
            {"id": "123456789", "value": "localisation_pac", "mapping": {"foo": "bar"}}
        ],
    )
    demarche.clean()


def test_get_demarche_numerique_value_sources(bizous_town_center):  # noqa: F811
    """Test get_demarche_numerique_value_sources method"""
    other_map = MapFactory()
    sites_proteges_regulation = RegulationFactory(
        regulation="sites_proteges_haie",
        has_perimeters=True,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesProtegesRegulation",
    )
    spr_perimeter_bizou = PerimeterFactory(
        name="Bizous",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )
    spr_perimeter_bizou_MH = PerimeterFactory(
        name="MH",
        activation_map=bizous_town_center,
        regulations=[sites_proteges_regulation],
    )
    spr_perimeter_other = PerimeterFactory(
        name="Other",
        activation_map=other_map,
        regulations=[sites_proteges_regulation],
    )
    CriterionFactory(
        title="Sites Patrimoniaux Remarquables",
        backend_title="SPR Haies > bizou",
        regulation=sites_proteges_regulation,
        perimeter=spr_perimeter_bizou,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.SitesPatrimoniauxRemarquablesHaieHru",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    CriterionFactory(
        title="Monuments historiques",
        backend_title="MH Haies > bizou2",
        regulation=sites_proteges_regulation,
        perimeter=spr_perimeter_bizou_MH,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.MonumentsHistoriquesHaieHru",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    CriterionFactory(
        title="Monuments historiques",
        backend_title="SPR Haies > bizou",
        regulation=sites_proteges_regulation,
        perimeter=spr_perimeter_other,
        evaluator="envergo.moulinette.regulations.sites_proteges_haie.MonumentsHistoriquesHaieHru",
        activation_map=bizous_town_center,
        activation_mode="hedges_intersection",
    )
    expected_results_criteria = {
        (
            "sites_proteges_haie.hru__mh_haie.result_code",
            "Code de résultat du critère MH Haies > bizou2 de la réglementation sites_proteges_haie",
        ),
        (
            "sites_proteges_haie.hru__spr_haie.result_code",
            "Code de résultat du critère SPR Haies > bizou de la réglementation sites_proteges_haie",
        ),
    }

    results = DemarcheConfig.get_demarche_numerique_value_sources()
    assert results["Résultats des critères"] == expected_results_criteria


@pytest.fixture
def qc_source_criterion():
    """A haie criterion exposing a « question complémentaire » (plan_gestion)."""
    regulation = HaieRegulationFactory(regulation="reserves_naturelles")
    return CriterionFactory(
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.reserves_naturelles.ReservesNaturellesRu",
    )


def test_value_sources_have_a_questions_complementaires_section(qc_source_criterion):
    """`ConfigHaie.clean` finds the QC sources by matching this section title.

    If you rename the section, update `qc_sources` in `ConfigHaie.clean` too.
    """
    sources = DemarcheConfig.get_demarche_numerique_value_sources()
    qc_sections = {k: v for k, v in sources.items() if "Questions complémentaires" in k}

    assert len(qc_sections) == 1
    assert "plan_gestion" in {
        key for section in qc_sections.values() for key, _ in section
    }


def test_demarchenumerique_config_qc_source_requires_a_default(
    qc_source_criterion,
):
    """A QC source has no systematic value, so the pre-fill config must give a default."""

    def build_config(field):
        return DemarcheConfig(
            demarche_numerique_number="123456789",
            pre_fill_config=[field],
        )

    with pytest.raises(ValidationError, match="question complémentaire"):
        build_config({"id": "123456789", "value": "plan_gestion"}).clean()

    build_config({"id": "123456789", "value": "plan_gestion", "default": "non"}).clean()
