import logging
from unittest.mock import patch

import pytest
from django.test import override_settings
from gql.transport.exceptions import TransportQueryError

from envergo.petitions.demarche_numerique.client import (
    DemarcheNumeriqueClient,
    DemarcheNumeriqueError,
)

pytestmark = pytest.mark.django_db

DN_SETTINGS = {
    "ENABLED": True,
    "GRAPHQL_API_URL": "https://example.org/graphql",
    "GRAPHQL_API_BEARER_TOKEN": "token",
}
QUERY = "query { dossier(number: 1) { id } }"


@pytest.mark.parametrize(
    "code,path,expected_level",
    [
        ("not_found", ["dossier"], logging.INFO),
        ("not_found", ["demarche"], logging.ERROR),
        ("internal_error", ["dossier"], logging.ERROR),
    ],
)
@override_settings(DEMARCHE_NUMERIQUE=DN_SETTINGS)
def test_execute_failure_log_level(code, path, expected_level, caplog):
    error = TransportQueryError(
        "boom",
        errors=[{"message": "boom", "path": path, "extensions": {"code": code}}],
    )
    client = DemarcheNumeriqueClient()
    with patch.object(client.client, "execute", side_effect=error):
        with caplog.at_level(
            logging.INFO, logger="envergo.petitions.demarche_numerique.client"
        ):
            with pytest.raises(DemarcheNumeriqueError):
                client.execute(QUERY)

    records = [r for r in caplog.records if "request failed" in r.getMessage()]
    assert [r.levelno for r in records] == [expected_level]
