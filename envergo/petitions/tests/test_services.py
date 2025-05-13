import datetime
import json
from dataclasses import asdict
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.petitions.regulations.conditionnalitepac import bcae8_get_instructors_info
from envergo.petitions.regulations.ep import ep_aisne_get_instructors_info
from envergo.petitions.services import (
    compute_instructor_informations,
    fetch_project_details_from_demarches_simplifiees,
)
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    GET_DOSSIER_FAKE_RESPONSE,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees(mock_post, haie_user, site):
    """Test fetch project details from démarches simplifiées"""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = GET_DOSSIER_FAKE_RESPONSE
    mock_post.return_value = mock_response

    config = ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()
    moulinette = petition_project.get_moulinette()

    dossier = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )
    assert dossier is not None

    project_details = compute_instructor_informations(
        petition_project, moulinette, site, "", haie_user
    )
    ds_data = project_details.ds_data

    assert ds_data.applicant_name == "Mme Hedy Lamarr"
    assert ds_data.city == "Laon (02000)"
    assert ds_data.pacage == "123456789"

    petition_project.refresh_from_db()
    assert petition_project.demarches_simplifiees_date_depot == datetime.datetime(
        2025, 3, 21, 10, 8, 34, tzinfo=datetime.timezone.utc
    )
    assert petition_project.demarches_simplifiees_last_sync is not None


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees_not_enabled(
    mock_post, caplog, haie_user, site
):
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert (
        len(
            [
                rec.message
                for rec in caplog.records
                if "Demarches Simplifiees is not enabled" in rec.message
            ]
        )
        > 0
    )
    fake_dossier = GET_DOSSIER_FAKE_RESPONSE.get("data", {}).get("dossier")
    assert details == fake_dossier


@patch("envergo.petitions.services.notify")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_if_config_is_incomplete(
    mock_notify, haie_user, site
):
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "Les identifiants des champs PACAGE et Commune principale ne sont pas renseignés"
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.services.notify")
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_API_error(
    mock_post, mock_notify, haie_user, site
):
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"an error": "occurred"}

    mock_post.return_value = mock_response
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "L'API de Démarches Simplifiées a retourné une erreur lors de la récupération du dossier"
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.services.notify")
@patch("requests.post")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_unexpected_response(
    mock_post, mock_notify, haie_user, site
):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"weirdely_formatted": "response"}}

    mock_post.return_value = mock_response
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = fetch_project_details_from_demarches_simplifiees(
        petition_project, config, site, "", haie_user
    )

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "La réponse de l'API de Démarches Simplifiées ne répond pas au format attendu."
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


def test_ep_aisne_get_instructors_info(france_map):  # noqa
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0691, "lng": 0.4423},
                ],
                "additionalData": {
                    "position": "interchamp",
                    "sur_talus": False,
                    "vieil_arbre": True,
                    "type_haie": "arbustive",
                    "proximite_point_eau": False,
                    "mode_plantation": "plantation",
                    "sur_parcelle_pac": True,
                    "sous_ligne_electrique": True,
                    "connexion_boisement": False,
                },
            },
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0691, "lng": 0.4423},
                ],
                "additionalData": {
                    "position": "interchamp",
                    "sur_talus": False,
                    "type_haie": "arbustive",
                    "proximite_point_eau": True,
                    "mode_destruction": "coupe_a_blanc",
                    "sur_parcelle_pac": True,
                    "recemment_plantee": False,
                    "connexion_boisement": True,
                },
            },
        ]
    )
    moulinette_data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
    }

    regulation = RegulationFactory(regulation="ep")
    [
        CriterionFactory(
            title="Espèces protégées",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesAisne",
            activation_map=france_map,
            activation_mode="department_centroid",
        ),
    ]
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    ConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesAisneForm",
    )

    moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
    info = ep_aisne_get_instructors_info(
        moulinette.ep.ep_aisne._evaluator, petition_project, moulinette
    )

    expected_json = """{"comment": null,
 "key_elements": ["onagre_number"],
 "label": "Espèces protégées",
 "other_items": null,
 "simulation_data": [{"label": "Calcul de la compensation attendue"},
                     {"comment": null,
                      "label": "Coefficient compensation",
                      "unit": null,
                      "value": 1.5},
                     {"label": "Situation des haies"},
                     {"comment": null,
                      "label": "Située sur une parcelle PAC",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "28\xa0m  • D1"},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "28\xa0m  • P1"}],
                                "display_result": true,
                                "result": true}},
                     {"comment": null,
                      "label": "Inter-champ",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "28\xa0m  • D1"},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "28\xa0m  • P1"}],
                                "display_result": true,
                                "result": true}},
                     {"comment": null,
                      "label": "Bordure de voirie ouverte à la circulation",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "0\xa0m "},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "0\xa0m "}],
                                "display_result": true,
                                "result": false}},
                     {"comment": null,
                      "label": "Autre (bord de chemin, bâtiment…)",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "0\xa0m "},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "0\xa0m "}],
                                "display_result": true,
                                "result": false}},
                     {"comment": null,
                      "label": "Mare à moins de 200\xa0m",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "0\xa0m "},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "0\xa0m "}],
                                "display_result": true,
                                "result": false}},
                     {"comment": null,
                      "label": "Contient un ou plusieurs vieux arbres, fissurés ou avec cavités",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "28\xa0m  • D1"}],
                                "display_result": true,
                                "result": true}},
                     {"comment": null,
                      "label": "Connectée à un boisement ou à une autre haie",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "0\xa0m "},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "28\xa0m  • P1"}],
                                "display_result": true,
                                "result": true}},
                     {"comment": null,
                      "label": "Mare ou ruisseau à moins de 10\xa0m",
                      "unit": null,
                      "value": {"details": [{"label": "Destruction",
                                             "unit": null,
                                             "value": "0\xa0m "},
                                            {"label": "Plantation",
                                             "unit": null,
                                             "value": "28\xa0m  • P1"}],
                                "display_result": true,
                                "result": true}},
                     {"comment": null,
                      "label": "Sous une ligne électrique ou téléphonique",
                      "unit": null,
                      "value": {"details": [{"label": "Plantation",
                                             "unit": null,
                                             "value": "0\xa0m "}],
                                "display_result": true,
                                "result": false}},
                     {"label": "Liste des espèces"},
                     "protected_species"],
 "slug": "ep"}"""
    assert asdict(info) == json.loads(expected_json)


def test_bcae8_get_instructors_info(france_map):  # noqa
    hedges = HedgeDataFactory(
        data=[
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0691, "lng": 0.4423},
                ],
                "additionalData": {
                    "position": "interchamp",
                    "sur_talus": False,
                    "vieil_arbre": True,
                    "type_haie": "arbustive",
                    "proximite_point_eau": False,
                    "mode_plantation": "plantation",
                    "sur_parcelle_pac": True,
                    "sous_ligne_electrique": True,
                    "connexion_boisement": False,
                },
            },
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0691, "lng": 0.4423},
                ],
                "additionalData": {
                    "position": "interchamp",
                    "sur_talus": False,
                    "type_haie": "arbustive",
                    "proximite_point_eau": True,
                    "mode_destruction": "coupe_a_blanc",
                    "sur_parcelle_pac": True,
                    "recemment_plantee": False,
                    "connexion_boisement": True,
                },
            },
        ]
    )
    moulinette_data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
    }

    regulation = RegulationFactory(regulation="conditionnalite_pac")
    CriterionFactory(
        title="Bonnes conditions agricoles et environnementales - Fiche VIII",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    ConfigHaieFactory()

    moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
    info = bcae8_get_instructors_info(
        moulinette.conditionnalite_pac.bcae8._evaluator, petition_project, moulinette
    )
    # noqa: E501
    expected_json = """{
  "slug": "bcae8",
  "label": "BCAE 8",
  "key_elements": [
    {
      "label": "Motif",
      "value": "\\n            Cr\\u00e9ation d\\u2019un acc\\u00e8s \\u00e0 la parcelle<br/>\\n            <span class=\\"fr-hint-text\\">\\n                Br\\u00e8che dans une haie pour cr\\u00e9er un chemin, permettre le passage d\\u2019engins\\u2026\\n            </span>\\n            ",
      "unit": null,
      "comment": null
    },
    {
      "label": "Total lin\\u00e9aire exploitation d\\u00e9clar\\u00e9",
      "value": "",
      "unit": "m",
      "comment": null
    },
    {
      "label": "Total lin\\u00e9aire d\\u00e9truit",
      "value": 28,
      "unit": "m",
      "comment": null
    },
    {
      "label": "Total lin\\u00e9aire plant\\u00e9",
      "value": 28,
      "unit": "m",
      "comment": null
    }
  ],
  "simulation_data": [
    {
      "label": "Total lin\\u00e9aire exploitation d\\u00e9clar\\u00e9",
      "value": "",
      "unit": "m",
      "comment": null
    },
    {
      "label": "Destruction",
      "items": [
        {
          "label": "Total lin\\u00e9aire \\u00e0 d\\u00e9truire sur parcelle PAC",
          "value": 28,
          "unit": "m",
          "comment": null
        },
        {
          "label": "D\\u00e9tail",
          "value": "28 m \\u22c5 D1",
          "unit": null,
          "comment": null
        },
        {
          "label": "Pourcentage lin\\u00e9aire \\u00e0 d\\u00e9truire / total lin\\u00e9aire exploitation",
          "value": "",
          "unit": "%",
          "comment": null
        }
      ]
    },
    {
      "label": "Plantation",
      "items": [
        {
          "label": "Total lin\\u00e9aire \\u00e0 planter sur parcelle PAC",
          "value": 28,
          "unit": "m",
          "comment": null
        },
        {
          "label": "D\\u00e9tail",
          "value": "28 m \\u22c5 P1",
          "unit": null,
          "comment": null
        },
        {
          "label": "Ratio de replantation",
          "value": 1.0,
          "unit": null,
          "comment": "Lin\\u00e9aire \\u00e0 planter / lin\\u00e9aire \\u00e0 d\\u00e9truire, sur parcelle PAC"
        }
      ]
    }
  ],
  "other_items": null,
  "comment": "Les d\\u00e9comptes de cette section n\'incluent que les haies d\\u00e9clar\\u00e9es sur parcelle PAC. Les alignements d\\u2019arbres sont \\u00e9galement exclus."
}"""  # noqa
    assert asdict(info) == json.loads(expected_json)
