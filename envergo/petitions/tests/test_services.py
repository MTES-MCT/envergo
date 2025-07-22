import datetime
from collections import OrderedDict
from decimal import Decimal
from unittest.mock import ANY, patch

import pytest
from django.test import override_settings
from gql.transport.exceptions import TransportQueryError

from envergo.analytics.models import Event
from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    ConfigHaieFactory,
    CriterionFactory,
    RegulationFactory,
)
from envergo.petitions.demarches_simplifiees.models import Dossier
from envergo.petitions.models import SESSION_KEY
from envergo.petitions.regulations.conditionnalitepac import (
    bcae8_get_instructor_view_context,
)
from envergo.petitions.regulations.ep import (
    ep_aisne_get_instructor_view_context,
    ep_normandie_get_instructor_view_context,
)
from envergo.petitions.services import (
    get_demarches_simplifiees_dossier,
    get_instructor_view_context,
)
from envergo.petitions.tests.factories import (
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    GET_DOSSIER_FAKE_RESPONSE,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_fetch_project_details_from_demarches_simplifiees(mock_post, haie_user, site):
    """Test fetch project details from démarches simplifiées"""
    # GIVEN a project with a valid dossier in Démarches Simplifiées
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    ConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()
    moulinette = petition_project.get_moulinette()

    # WHEN I fetch it from DS for the first time
    dossier = get_demarches_simplifiees_dossier(petition_project)
    # THEN the dossier is returned and an event is created
    assert dossier is not None
    assert Event.objects.get(category="dossier", event="depot", session_key=SESSION_KEY)

    # AND the project details are correctly populated
    project_details = get_instructor_view_context(petition_project, moulinette)

    assert project_details["applicant"] == "Mme Hedy Lamarr"
    assert project_details["city"] == "Laon (02000)"
    assert project_details["pacage"] == "123456789"

    petition_project.refresh_from_db()
    assert petition_project.demarches_simplifiees_date_depot == datetime.datetime(
        2025, 3, 21, 10, 8, 34, tzinfo=datetime.timezone.utc
    )
    assert petition_project.demarches_simplifiees_last_sync is not None

    # WHEN I fetch it again less than one hour later
    dossier = get_demarches_simplifiees_dossier(petition_project)
    # THEN the same dossier is returned from cache, and the DS Api is not called again
    assert dossier is not None
    mock_post.assert_called_once()

    # WHEN I fetch it again more than one hour later
    petition_project.demarches_simplifiees_last_sync = datetime.datetime.now(
        datetime.timezone.utc
    ) - datetime.timedelta(hours=2)
    petition_project.save()
    dossier = get_demarches_simplifiees_dossier(petition_project)
    # THEN the cache is not used, and the DS Api called
    assert dossier is not None
    assert mock_post.call_count == 2

    # GIVEN a new dossier in Draft status With an existing creation event
    petition_project = PetitionProjectFactory(reference="DEF456")
    Event.objects.create(
        category="dossier",
        event="creation",
        session_key="a given user",
        metadata={"reference": "DEF456"},
        site_id=site.id,
    )

    # WHEN I synchronize it with DS for the first time
    get_demarches_simplifiees_dossier(petition_project)

    # THEN an event is created with the same session key as the creation event
    assert Event.objects.get(
        category="dossier", event="depot", session_key="a given user"
    )
    assert mock_post.call_count == 3


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
def test_fetch_project_details_from_demarches_simplifiees_not_enabled(
    caplog, haie_user
):
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = get_demarches_simplifiees_dossier(petition_project)

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
    assert details == Dossier.from_dict(fake_dossier)


@patch("envergo.petitions.services.notify")
def test_get_instructor_view_context_should_notify_if_config_is_incomplete(
    mock_notify, haie_user
):
    petition_project = PetitionProjectFactory()
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
                    "interchamp": True,
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
                    "interchamp": True,
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
    ConfigHaieFactory()
    moulinette_data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
    }
    moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
    get_instructor_view_context(petition_project, moulinette)

    args, kwargs = mock_notify.call_args
    assert (
        "Les identifiants des champs PACAGE, commune principale et/ou structure ne sont pas renseignés"
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.demarches_simplifiees.client.notify")
@patch("gql.client.Client.execute")
def test_fetch_project_details_from_demarches_simplifiees_should_notify_API_error(
    mock_post, mock_notify, haie_user
):
    mock_post.side_effect = TransportQueryError(
        "Mocked transport error", errors=[{"message": "Mocked error"}]
    )

    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = get_demarches_simplifiees_dossier(petition_project)

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "L'API de Démarches Simplifiées a retourné une erreur lors de la récupération du dossier"
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("envergo.petitions.demarches_simplifiees.client.notify")
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_fetch_project_details_from_demarches_simplifiees_should_notify_unexpected_response(
    mock_post, mock_notify, haie_user
):
    mock_post.return_value = {"data": {"weirdely_formatted": "response"}}
    petition_project = PetitionProjectFactory()
    config = ConfigHaieFactory()
    config.demarches_simplifiees_city_id = "Q2hhbXAtNDcyOTE4Nw=="
    config.demarches_simplifiees_pacage_id = "Q2hhbXAtNDU0MzkzOA=="

    details = get_demarches_simplifiees_dossier(petition_project)

    assert details is None

    args, kwargs = mock_notify.call_args
    assert (
        "La réponse de l'API de Démarches Simplifiées ne répond pas au format attendu."
        in args[0]
    )
    assert "haie" in args[1]

    mock_notify.assert_called_once()


def test_ep_aisne_get_instructor_view_context(france_map):  # noqa
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
                    "interchamp": True,
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
                    "interchamp": True,
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
    CriterionFactory(
        title="Espèces protégées",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesAisne",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    ConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesAisneForm",
    )

    moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
    info = ep_aisne_get_instructor_view_context(
        moulinette.ep.ep_aisne._evaluator, petition_project, moulinette
    )

    expected_result = {
        "hedges_properties": {
            "connexion_boisement": {
                "TO_PLANT": [ANY],
                "TO_REMOVE": [],
                "label": "Connectée à un " "boisement ou à une " "autre haie",
            },
            "bord_voie": {
                "TO_PLANT": [],
                "TO_REMOVE": [],
                "label": "Bord de route, voie ou chemin " "ouvert au public",
            },
            "proximite_mare": {
                "TO_PLANT": [],
                "TO_REMOVE": [],
                "label": "Mare à moins de 200\xa0m",
            },
            "proximite_point_eau": {
                "TO_PLANT": [ANY],
                "TO_REMOVE": [],
                "label": "Mare ou ruisseau à " "moins de 10\xa0m",
            },
            "sous_ligne_electrique": {
                "TO_PLANT": [],
                "TO_REMOVE": None,
                "label": "Sous une ligne " "électrique ou " "téléphonique",
            },
            "vieil_arbre": {
                "TO_PLANT": None,
                "TO_REMOVE": [ANY],
                "label": "Contient un ou plusieurs "
                "vieux arbres, fissurés ou "
                "avec cavités",
            },
        },
        "replantation_coefficient": Decimal("1.5"),
    }
    assert info == expected_result


def test_ep_normandie_get_instructor_view_context(france_map):  # noqa
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
                    "interchamp": True,
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
                    "interchamp": True,
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
    CriterionFactory(
        title="Espèces protégées",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesNormandie",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    ConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesCalvadosForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesCalvadosForm",
    )

    moulinette = MoulinetteHaie(moulinette_data, moulinette_data)
    info = ep_normandie_get_instructor_view_context(
        moulinette.ep.ep_normandie._evaluator, petition_project, moulinette
    )

    expected_result = {
        "HEDGE_KEYS": OrderedDict(
            [
                ("mixte", "Type 5 (mixte)"),
                ("alignement", "Type 4 (alignement)"),
                ("arbustive", "Type 3 (arbustive)"),
                ("buissonnante", "Type 2 (buissonnante)"),
                ("degradee", "Type 1 (dégradée)"),
            ]
        ),
        "hedges_properties": {
            "essences_non_bocageres": {
                "TO_PLANT": [],
                "TO_REMOVE": [],
                "label": "Composée " "d'essences non " "bocagères",
            },
            "bord_voie": {
                "TO_PLANT": [],
                "TO_REMOVE": [],
                "label": "Bord de route, voie ou chemin " "ouvert au public",
            },
            "interchamp": {
                "TO_PLANT": [ANY],
                "TO_REMOVE": [ANY],
                "label": "Haie inter-champ",
            },
            "proximite_mare": {
                "TO_PLANT": [],
                "TO_REMOVE": [],
                "label": "Mare à moins de 200\xa0m",
            },
            "recemment_plantee": {
                "TO_PLANT": None,
                "TO_REMOVE": [],
                "label": "Haie récemment plantée",
            },
            "sous_ligne_electrique": {
                "TO_PLANT": [],
                "TO_REMOVE": None,
                "label": "Sous une ligne " "électrique ou " "téléphonique",
            },
            "sur_talus": {"TO_PLANT": [], "TO_REMOVE": [], "label": "Haie sur talus"},
            "vieil_arbre": {
                "TO_PLANT": None,
                "TO_REMOVE": [ANY],
                "label": "Contient un ou plusieurs "
                "vieux arbres, fissurés ou "
                "avec cavités",
            },
        },
        "quality_condition": {
            "LC": {
                "alignement": 0,
                "arbustive": 11.020243366815471,
                "buissonnante": 0,
                "degradee": 0,
                "mixte": 0,
            },
            "LP": {"arbustive": 27.55060841703869},
            "LPm": {
                "alignement": 0,
                "arbustive": 38.57085178385416,
                "buissonnante": 0,
                "degradee": 0,
                "mixte": 0,
            },
            "lm": 11.020243366815471,
            "lp": 27.55060841703869,
            "lpm": 39,
            "reduced_lpm": 31,
        },
        "replantation_coefficient": Decimal("1.40"),
    }
    assert info == expected_result


def test_bcae8_get_instructor_view_context(france_map):  # noqa
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
                    "interchamp": True,
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
                    "interchamp": True,
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
    info = bcae8_get_instructor_view_context(
        moulinette.conditionnalite_pac.bcae8._evaluator, petition_project, moulinette
    )
    # noqa: E501
    expected_result = {
        "lineaire_detruit_pac": 27.55060841703869,
        "lineaire_to_plant_pac": 27.55060841703869,
        "motif": "\n"
        "            Création d’un accès à la parcelle<br/>\n"
        '            <span class="fr-hint-text">\n'
        "                Brèche dans une haie pour créer un chemin, "
        "permettre le passage d’engins…\n"
        "            </span>\n"
        "            ",
        "pac_destruction_detail": [ANY],
        "pac_plantation_detail": [ANY],
        "percentage_pac": "",
        "replanting_ratio": 1.0,
        "replanting_ratio_comment": "Linéaire à planter / linéaire à détruire, sur "
        "parcelle PAC",
    }
    assert info == expected_result
