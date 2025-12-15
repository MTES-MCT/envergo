import datetime
from collections import OrderedDict
from decimal import Decimal
from unittest.mock import ANY, patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from gql.transport.exceptions import TransportQueryError

from envergo.analytics.models import Event
from envergo.geodata.conftest import france_map  # noqa
from envergo.hedges.tests.factories import HedgeDataFactory
from envergo.moulinette.models import MoulinetteHaie
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)
from envergo.petitions.demarches_simplifiees.models import Dossier, DossierState
from envergo.petitions.models import SESSION_KEY
from envergo.petitions.regulations.alignementarbres import (
    alignement_arbres_get_instructor_view_context,
)
from envergo.petitions.regulations.conditionnalitepac import (
    bcae8_get_instructor_view_context,
)
from envergo.petitions.regulations.ep import (
    ep_aisne_get_instructor_view_context,
    ep_normandie_get_instructor_view_context,
)
from envergo.petitions.services import (
    compute_instructor_informations_ds,
    get_context_from_ds,
    get_demarches_simplifiees_dossier,
    get_messages_and_senders_from_ds,
    send_message_dossier_ds,
    update_demarches_simplifiees_status,
)
from envergo.petitions.tests.factories import (
    CREATEUPLOAD_FAKE_RESPONSE,
    DEMARCHES_SIMPLIFIEES_FAKE,
    DEMARCHES_SIMPLIFIEES_FAKE_DISABLED,
    DOSSIER_SEND_MESSAGE_ATTACHMENT_FAKE_RESPONSE,
    DOSSIER_SEND_MESSAGE_FAKE_RESPONSE,
    DOSSIER_SEND_MESSAGE_FAKE_RESPONSE_ERROR,
    FILE_TEST_PATH,
    GET_DOSSIER_FAKE_RESPONSE,
    GET_DOSSIER_MESSAGES_FAKE_RESPONSE,
    PetitionProjectFactory,
)

pytestmark = pytest.mark.django_db


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch(
    "envergo.petitions.demarches_simplifiees.client.DemarchesSimplifieesClient.execute"
)
def test_fetch_project_details_from_demarches_simplifiees(mock_post, haie_user, site):
    """Test fetch project details from démarches simplifiées"""
    # GIVEN a project with a valid dossier in Démarches Simplifiées
    mock_post.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()
    moulinette = petition_project.get_moulinette()

    # WHEN I fetch it from DS for the first time
    dossier = get_demarches_simplifiees_dossier(petition_project)
    # THEN the dossier is returned and an event is created
    assert dossier is not None
    assert Event.objects.get(category="demande", event="depot", session_key=SESSION_KEY)

    # AND the project details are correctly populated
    project_details = get_context_from_ds(petition_project, moulinette)

    assert project_details["applicant"] == "Mme LAMARR Hedy"
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
        category="demande",
        event="creation",
        session_key="a given user",
        metadata={"reference": "DEF456"},
        site_id=site.id,
    )

    # WHEN I synchronize it with DS for the first time
    get_demarches_simplifiees_dossier(petition_project)

    # THEN an event is created with the same session key as the creation event
    assert Event.objects.get(
        category="demande", event="depot", session_key="a given user"
    )
    assert mock_post.call_count == 3


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
def test_fetch_project_details_from_demarches_simplifiees_not_enabled(
    caplog, haie_user
):
    petition_project = PetitionProjectFactory()
    config = DCConfigHaieFactory()
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


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
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
    DCConfigHaieFactory()
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
    }
    moulinette_data = {"initial": data, "data": data}
    moulinette = MoulinetteHaie(moulinette_data)
    get_context_from_ds(petition_project, moulinette)

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
    config = DCConfigHaieFactory()
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
    config = DCConfigHaieFactory()
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


@patch("envergo.petitions.services.get_demarches_simplifiees_dossier")
def test_compute_instructor_information(mock_get_dossier):
    """Test compute instructor information from démarche simplifiées dossier data"""
    mock_get_dossier.return_value = Dossier.from_dict(
        GET_DOSSIER_FAKE_RESPONSE["data"]["dossier"]
    )

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()

    # When I compute instructor information for a given petition project
    project_details = compute_instructor_informations_ds(petition_project)

    # Then I should have header sections from demarche champ descriptors
    header_sections = project_details.header_sections
    assert header_sections == [
        "Identité",
        "Description du projet",
        "Autorisation du propriétaire",
        "Conditionnalité PAC – BCAE8",
        "Réglementation «\xa0Espèces protégées\xa0»",
        "Description des haies à détruire",
        "Description de la plantation",
    ]

    # Then I should have correct data for each field type
    champs = project_details.champs
    [yesno_champ_yes] = [
        c
        for c in champs
        if c.label
        == "Êtes-vous propriétaire de tous les terrains sur lesquels se situent les haies à détruire ?"
    ]
    [yesno_champ_no] = [
        c for c in champs if c.label == "Présence de vieux arbres fissurés ou à cavité"
    ]
    [checkbox_champ_checked] = [
        c
        for c in champs
        if c.label
        == "Je m'engage à ne démarrer mes travaux qu'en cas d'acceptation de ma demande"
    ]

    assert yesno_champ_yes.value == "oui"
    assert yesno_champ_no.value == "non"
    assert checkbox_champ_checked.value == "oui"


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
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
        "numero_pacage": "123456789",
    }
    moulinette_data = {"initial": data, "data": data}

    regulation = RegulationFactory(regulation="ep")
    CriterionFactory(
        title="Espèces protégées",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesAisne",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    DCConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesAisneForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesAisneForm",
    )

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()
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
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
        "numero_pacage": "123456789",
    }
    moulinette_data = {"initial": data, "data": data}

    regulation = RegulationFactory(regulation="ep")
    CriterionFactory(
        title="Espèces protégées",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.ep.EspecesProtegeesNormandie",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    DCConfigHaieFactory(
        hedge_to_plant_properties_form="envergo.hedges.forms.HedgeToPlantPropertiesCalvadosForm",
        hedge_to_remove_properties_form="envergo.hedges.forms.HedgeToRemovePropertiesCalvadosForm",
    )

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()
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
    data = {
        "motif": "chemin_acces",
        "reimplantation": "replantation",
        "localisation_pac": "oui",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
        "lineaire_total": 5000,
        "numero_pacage": "123456789",
    }
    moulinette_data = {"initial": data, "data": data}

    regulation = RegulationFactory(regulation="conditionnalite_pac")
    CriterionFactory(
        title="Bonnes conditions agricoles et environnementales - Fiche VIII",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    DCConfigHaieFactory()

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()
    info = bcae8_get_instructor_view_context(
        moulinette.conditionnalite_pac.bcae8._evaluator, petition_project, moulinette
    )
    # noqa: E501
    expected_result = {
        "lineaire_detruit_pac": 27.55060841703869,
        "lineaire_to_plant_pac": 27.55060841703869,
        "pac_destruction_detail": [ANY],
        "pac_plantation_detail": [ANY],
        "percentage_pac": ANY,
        "replanting_ratio": 1.0,
        "replanting_ratio_comment": "Linéaire à planter / linéaire à détruire, sur "
        "parcelle PAC",
    }
    assert info == expected_result


def test_aa_get_instructor_view_context(france_map):  # noqa
    """Test alignement arbre get instructor view context"""

    hedges = HedgeDataFactory(
        data=[
            {
                "id": "P1",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.0693, "lng": 0.4421},
                    {"lat": 43.0691, "lng": 0.4423},
                ],
                "additionalData": {
                    "bord_voie": True,
                    "type_haie": "alignement",
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "connexion_boisement": False,
                    "proximite_point_eau": False,
                    "sous_ligne_electrique": False,
                },
            },
            {
                "id": "P2",
                "type": "TO_PLANT",
                "latLngs": [
                    {"lat": 43.0695, "lng": 0.4423},
                    {"lat": 43.0693, "lng": 0.4426},
                ],
                "additionalData": {
                    "bord_voie": False,
                    "type_haie": "alignement",
                    "proximite_mare": False,
                    "sur_parcelle_pac": False,
                    "connexion_boisement": False,
                    "proximite_point_eau": False,
                    "sous_ligne_electrique": False,
                },
            },
            {
                "id": "D1",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0698, "lng": 0.4423},
                    {"lat": 43.0695, "lng": 0.4426},
                ],
                "additionalData": {
                    "bord_voie": True,
                    "type_haie": "alignement",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "mode_destruction": "arrachage",
                    "sur_parcelle_pac": False,
                    "connexion_boisement": False,
                    "proximite_point_eau": False,
                },
            },
            {
                "id": "D2",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0698, "lng": 0.4426},
                    {"lat": 43.0695, "lng": 0.443},
                ],
                "additionalData": {
                    "bord_voie": False,
                    "type_haie": "alignement",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "mode_destruction": "arrachage",
                    "sur_parcelle_pac": False,
                    "connexion_boisement": False,
                    "proximite_point_eau": False,
                },
            },
            {
                "id": "D3",
                "type": "TO_REMOVE",
                "latLngs": [
                    {"lat": 43.0700, "lng": 0.4426},
                    {"lat": 43.0698, "lng": 0.4428},
                ],
                "additionalData": {
                    "bord_voie": True,
                    "type_haie": "arbustive",
                    "vieil_arbre": False,
                    "proximite_mare": False,
                    "mode_destruction": "arrachage",
                    "sur_parcelle_pac": False,
                    "connexion_boisement": False,
                    "proximite_point_eau": False,
                },
            },
        ]
    )

    data = {
        "motif": "amelioration_culture",
        "reimplantation": "replantation",
        "localisation_pac": "non",
        "haies": hedges,
        "travaux": "destruction",
        "element": "haie",
        "department": 44,
    }
    moulinette_data = {"initial": data, "data": data}

    regulation = RegulationFactory(regulation="alignement_arbres")
    CriterionFactory(
        title="Alignements arbres L350-3",
        regulation=regulation,
        evaluator="envergo.moulinette.regulations.alignementarbres.AlignementsArbres",
        activation_map=france_map,
        activation_mode="department_centroid",
    )
    petition_project = PetitionProjectFactory(hedge_data=hedges)
    DCConfigHaieFactory()

    moulinette = MoulinetteHaie(moulinette_data)
    assert moulinette.is_valid(), moulinette.form_errors()
    context = alignement_arbres_get_instructor_view_context(
        moulinette.alignement_arbres.alignement_arbres._evaluator,
        petition_project,
        moulinette,
    )
    assert "Amélioration des conditions d’exploitation agricole" in context["motif"]

    aa_bord_voie_destruction_hedge = context["aa_bord_voie_destruction_detail"][0]
    assert (
        aa_bord_voie_destruction_hedge.length
        == context["length_to_remove_aa_bord_voie"]
    )
    assert aa_bord_voie_destruction_hedge.type == "TO_REMOVE"
    assert aa_bord_voie_destruction_hedge.hedge_type == "alignement"
    assert aa_bord_voie_destruction_hedge.prop("bord_voie") is True

    aa_non_bord_voie_destruction_hedge = context["aa_non_bord_voie_destruction_detail"][
        0
    ]
    assert (
        aa_non_bord_voie_destruction_hedge.length
        == context["length_to_remove_aa_non_bord_voie"]
    )
    assert aa_non_bord_voie_destruction_hedge.type == "TO_REMOVE"
    assert aa_non_bord_voie_destruction_hedge.hedge_type == "alignement"
    assert aa_non_bord_voie_destruction_hedge.prop("bord_voie") is False

    non_aa_bord_voie_destruction_hedge = context["non_aa_bord_voie_destruction_detail"][
        0
    ]
    assert (
        non_aa_bord_voie_destruction_hedge.length
        == context["length_to_remove_non_aa_bord_voie"]
    )
    assert non_aa_bord_voie_destruction_hedge.type == "TO_REMOVE"
    assert non_aa_bord_voie_destruction_hedge.hedge_type == "arbustive"
    assert non_aa_bord_voie_destruction_hedge.prop("bord_voie") is True

    aa_bord_voie_to_plant_hedge = context["aa_bord_voie_plantation_detail"][0]
    assert aa_bord_voie_to_plant_hedge.length == context["length_to_plant_aa_bord_voie"]
    assert aa_bord_voie_to_plant_hedge.type == "TO_PLANT"
    assert aa_bord_voie_to_plant_hedge.hedge_type == "alignement"
    assert aa_bord_voie_to_plant_hedge.prop("bord_voie") is True


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("gql.Client.execute")
def test_get_message_project_via_demarches_simplifiees(
    mock_gql_execute, haie_user, site
):
    """Test send message for project via demarches simplifiées"""
    # GIVEN a project with a valid dossier in Démarches Simplifiées
    mock_gql_execute.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()

    # Fetch project from DS to create it
    dossier = get_demarches_simplifiees_dossier(petition_project)
    assert dossier.id == "RG9zc2llci0yMzE3ODQ0Mw=="

    # WHEN I get messages for this dossier
    mock_gql_execute.return_value = GET_DOSSIER_MESSAGES_FAKE_RESPONSE["data"]
    messages, instructor_emails, petitioner_email = get_messages_and_senders_from_ds(
        petition_project
    )
    # THEN Messages are returned
    assert len(messages) == 8
    assert instructor_emails == ["instructeur@guh.gouv.fr"]
    assert petitioner_email == "hedy.lamarr@example.com"


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("gql.Client.execute")
def test_send_message_project_via_demarches_simplifiees(
    mock_gql_execute, haie_user, site
):
    """Test send message for project via demarches simplifiées"""

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()

    # Fetch project from DS to create it
    mock_gql_execute.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]
    dossier = get_demarches_simplifiees_dossier(petition_project)
    assert dossier.id == "RG9zc2llci0yMzE3ODQ0Mw=="

    # WHEN I send message for this dossier
    mock_gql_execute.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE["data"]
    message_body = "Bonjour ! Un nouveau message"
    result = send_message_dossier_ds(petition_project, message_body)

    # THEN messages has this new message
    assert result == {
        "clientMutationId": "1234",
        "errors": None,
        "message": {"body": "Bonjour ! Un nouveau message"},
    }

    # WHEN I send malformated
    mock_gql_execute.side_effect = None
    mock_gql_execute.return_value = DOSSIER_SEND_MESSAGE_FAKE_RESPONSE_ERROR["data"]
    message_body = "Bonjour ! Un nouveau message"
    result = send_message_dossier_ds(petition_project, message_body)

    # THEN I receive an error
    assert result is None


@pytest.mark.urls("config.urls_haie")
@override_settings(ENVERGO_HAIE_DOMAIN="testserver")
@override_settings(ENVERGO_AMENAGEMENT_DOMAIN="somethingelse")
@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE)
@patch("requests.sessions.Session.request")
@patch("gql.Client.execute")
def test_send_message_project_via_demarches_simplifiees_with_attachments(
    mock_gql_execute, mock_request_put, haie_user, site
):
    """Test send message for project via demarches simplifiées"""

    DCConfigHaieFactory(
        demarches_simplifiees_city_id="Q2hhbXAtNDcyOTE4Nw==",
        demarches_simplifiees_pacage_id="Q2hhbXAtNDU0MzkzOA==",
    )

    petition_project = PetitionProjectFactory()

    # Fetch project from DS to create it
    mock_gql_execute.return_value = GET_DOSSIER_FAKE_RESPONSE["data"]
    dossier = get_demarches_simplifiees_dossier(petition_project)
    assert dossier.id == "RG9zc2llci0yMzE3ODQ0Mw=="

    # WHEN I send message for this dossier with attachment
    mock_gql_execute.side_effect = [
        CREATEUPLOAD_FAKE_RESPONSE["data"],
        DOSSIER_SEND_MESSAGE_ATTACHMENT_FAKE_RESPONSE["data"],
    ]
    mock_request_put.result = "lala"

    message_body = "Bonjour ! Un nouveau message"
    attachment = SimpleUploadedFile(FILE_TEST_PATH.name, FILE_TEST_PATH.read_bytes())
    result = send_message_dossier_ds(
        petition_project, message_body, attachment_file=attachment
    )

    # THEN messages has this new message
    assert result == {
        "clientMutationId": "1234",
        "errors": None,
        "message": {"body": "Bonjour ! Un nouveau message"},
        "attachments": [
            {
                "__typename": "File",
                "filename": "Coriandrum_sativum.jpg",
                "contentType": "image/jpeg",
                "checksum": "RiNssRjMcFaITvQMLk6zNw==",
                "byteSize": "21053",
                "url": "https://upload.wikimedia.org/wikipedia/commons/1/13/Coriandrum_sativum_-_K%C3%B6hler%E2%80%93s_Medizinal-Pflanzen",  # noqa: 501
                "createdAt": "2025-07-17T17:25:13+02:00",
            }
        ],
    }


@override_settings(DEMARCHES_SIMPLIFIEES=DEMARCHES_SIMPLIFIEES_FAKE_DISABLED)
def test_update_demarches_simplifiees_state():
    # GIVEN a petition project in "en construction" state
    petition_project = PetitionProjectFactory(
        demarches_simplifiees_state="en_construction"
    )

    # WHEN I update its status to "en instruction"
    update_demarches_simplifiees_status(
        petition_project, DossierState.en_instruction.value
    )

    # THEN the status is updated
    petition_project.refresh_from_db()
    assert (
        petition_project.demarches_simplifiees_state
        == DossierState.en_instruction.value
    )
    assert petition_project.prefetched_dossier.state == DossierState.en_instruction

    # WHEN I update its status to "Accepté"
    update_demarches_simplifiees_status(petition_project, DossierState.accepte.value)

    # THEN the status is updated
    petition_project.refresh_from_db()
    assert petition_project.demarches_simplifiees_state == DossierState.accepte.value
    assert petition_project.prefetched_dossier.state == DossierState.accepte

    # WHEN I update its status to "Refusé"
    update_demarches_simplifiees_status(petition_project, DossierState.refuse.value)

    # THEN the status is updated
    petition_project.refresh_from_db()
    assert petition_project.demarches_simplifiees_state == DossierState.refuse.value
    assert petition_project.prefetched_dossier.state == DossierState.refuse

    # WHEN I update its status to "Classé sans suite"
    update_demarches_simplifiees_status(petition_project, DossierState.sans_suite.value)

    # THEN the status is updated
    petition_project.refresh_from_db()
    assert petition_project.demarches_simplifiees_state == DossierState.sans_suite.value
    assert petition_project.prefetched_dossier.state == DossierState.sans_suite
