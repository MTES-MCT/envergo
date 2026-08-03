"""Tests for the « Éviter / réduire » acknowledgment block on the haie form.

The block appears below the additional questions when the project removes
hedges whose category is RU or HRU. It gates the form submission behind a
"J'ai compris" checkbox whose value is not part of the simulation: it must
never reach the result urls, and result pages must never require it.
"""

import decimal
import re
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.urls import reverse

from envergo.analytics.models import Event
from envergo.hedges.models import HedgeCategory
from envergo.hedges.tests.factories import HedgeDataFactory, HedgeFactory
from envergo.moulinette.forms import MOTIF_CHOICES
from envergo.moulinette.tests.factories import (
    CriterionFactory,
    DCConfigHaieFactory,
    RegulationFactory,
)

pytestmark = pytest.mark.haie

BLOCK_TITLE = "Évitement et réduction des impacts"
CHECKBOX_NAME = "eviter_reduire"
MARKER_NAME = "eviter_reduire_displayed"
ACK_ERROR = "Vous devez confirmer avoir pris connaissance de cette information."
FORM_ERROR = (
    "Nous n'avons pas pu traiter votre demande car le formulaire contient des erreurs."
)
ALL_MOTIFS = [key for key, _ in MOTIF_CHOICES]

TRIAGE_PARAMS = {
    "department": "44",
    "element": "haie",
    "travaux": "destruction",
    "contexte": "non",
}


@pytest.fixture(autouse=True)
def eviter_reduire_enabled(settings):
    settings.HAIE_EVITER_REDUIRE_ENABLED = True


@pytest.fixture(autouse=True)
def conditionnalite_pac_criteria(loire_atlantique_map):  # noqa
    """Activate the BCAE8 criterion, the source of real additional questions."""
    regulation = RegulationFactory(
        regulation="conditionnalite_pac",
        evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8Regulation",
    )
    return [
        CriterionFactory(
            title="Bonnes conditions agricoles et environnementales - Fiche VIII",
            regulation=regulation,
            evaluator="envergo.moulinette.regulations.conditionnalitepac.Bcae8Hru",
            activation_map=loire_atlantique_map,
            activation_mode="department_centroid",
        ),
    ]


# The helpers disable sur_parcelle_pac: it does not affect the hedge
# category, but a PAC hedge would pull the BCAE8 additional questions
# into the flow.


def ru_hedge():
    """A hedge of category RU (non-alignement, no urban property)."""
    return HedgeFactory(additionalData__sur_parcelle_pac=False)


def hru_hedge():
    """A hedge of category HRU (alignement not along a road)."""
    return HedgeFactory(
        additionalData__type_haie="alignement",
        additionalData__bord_voie=False,
        additionalData__sur_parcelle_pac=False,
    )


def l350_3_hedge():
    """A hedge of category L350-3 (alignement along a road)."""
    return HedgeFactory(
        additionalData__type_haie="alignement",
        additionalData__bord_voie=True,
        additionalData__sur_parcelle_pac=False,
    )


def simulation_data(hedges, **overrides):
    """Valid main form data that triggers no BCAE8 additional question."""
    data = {
        **TRIAGE_PARAMS,
        "motif": "amelioration_culture",
        "reimplantation": "remplacement",
        "localisation_pac": "non",
        "haies": str(hedges.id),
    }
    data.update(overrides)
    return data


def form_url(params=None):
    url = reverse("moulinette_form")
    return f"{url}?{urlencode(params or TRIAGE_PARAMS)}"


def checkbox_tag(content):
    """Extract the rendered acknowledgment checkbox input tag."""
    match = re.search(rf'<input[^>]*name="{CHECKBOX_NAME}"[^>]*>', content)
    return match.group(0) if match else None


def motif_variant_tag(content, motif):
    """Extract the opening tag of the message variant for the given motif."""
    match = re.search(rf'<[a-z]+[^>]*data-motif="{motif}"[^>]*>', content)
    return match.group(0) if match else None


# Display rules


def test_block_absent_on_pristine_form(client):
    """The block does not show while the main form has no valid data."""
    DCConfigHaieFactory()

    res = client.get(form_url())

    assert res.status_code == 200
    assert BLOCK_TITLE not in res.content.decode()


def test_block_displayed_on_prefilled_form(client):
    """A form prefilled with valid url data shows the block, without error."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])

    res = client.get(form_url(simulation_data(hedges)))

    content = res.content.decode()
    assert BLOCK_TITLE in content
    tag = checkbox_tag(content)
    assert tag is not None
    assert "checked" not in tag
    assert MARKER_NAME in content
    assert ACK_ERROR not in content


def test_block_absent_for_pure_l350_3_project(client):
    """A single-category L350-3 project is the only case without the block."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[l350_3_hedge(), l350_3_hedge()])

    res = client.get(form_url(simulation_data(hedges)))

    assert BLOCK_TITLE not in res.content.decode()


def test_block_displayed_for_hru_project(client):
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[hru_hedge()])

    res = client.get(form_url(simulation_data(hedges)))

    assert BLOCK_TITLE in res.content.decode()


def test_block_displayed_for_mixed_categories_project(client):
    """One RU or HRU hedge among L350-3 hedges is enough to show the block."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[l350_3_hedge(), ru_hedge()])

    res = client.get(form_url(simulation_data(hedges)))

    assert BLOCK_TITLE in res.content.decode()


# Submission flow


def test_first_submission_redirects_to_display_the_block(client):
    """A valid submission missing the acknowledgment redisplays the form.

    Like the additional questions flow: redirect to the form url with the
    submitted values as parameters, and no validation error yet.
    """
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])

    res = client.post(form_url(), simulation_data(hedges))

    assert res.status_code == 302
    location = res["Location"]
    assert location.startswith(reverse("moulinette_form"))
    assert location.endswith("#eviter-reduire")
    assert CHECKBOX_NAME not in location
    assert MARKER_NAME not in location

    res = client.get(location.split("#")[0])
    content = res.content.decode()
    assert BLOCK_TITLE in content
    assert ACK_ERROR not in content


def test_resubmission_without_checking_shows_the_error(client):
    """Once the block was displayed (marker posted), the checkbox is required."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])
    data = simulation_data(hedges, **{MARKER_NAME: "true"})

    res = client.post(form_url(), data)

    assert res.status_code == 200
    content = res.content.decode()
    assert FORM_ERROR in content
    assert ACK_ERROR in content

    # The error event carries the acknowledgment error, even though the
    # acknowledgment form is not part of the moulinette forms
    error_event = Event.objects.get(category="erreur", event="formulaire-simu")
    assert CHECKBOX_NAME in error_event.metadata["errors"]


def test_checked_submission_reaches_the_result(client):
    """Acknowledging lets the submission through, without leaking to the url."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])
    data = simulation_data(hedges, **{MARKER_NAME: "true", CHECKBOX_NAME: "on"})

    res = client.post(form_url(), data)

    assert res.status_code == 302
    location = res["Location"]
    assert location.startswith("/simulateur/resultat/")
    assert CHECKBOX_NAME not in location
    assert MARKER_NAME not in location


def test_pure_l350_3_submission_is_not_gated(client):
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[l350_3_hedge()])

    res = client.post(form_url(), simulation_data(hedges))

    assert res.status_code == 302
    assert res["Location"].startswith("/simulateur/resultat/")


def test_block_appears_with_additional_questions_in_a_single_round_trip(client):
    """The block and the additional questions display together, not in sequence."""
    DCConfigHaieFactory()
    # Default hedge is RU and on a PAC parcel: BCAE8 questions will trigger
    hedges = HedgeDataFactory(hedges=[HedgeFactory()])
    data = simulation_data(hedges, localisation_pac="oui")

    res = client.post(form_url(), data)

    assert res.status_code == 302
    location = res["Location"]
    assert location.startswith(reverse("moulinette_form"))
    assert "#additional-forms" in location

    res = client.get(location.split("#")[0])
    content = res.content.decode()
    assert "Questions complémentaires" in content
    assert BLOCK_TITLE in content
    assert ACK_ERROR not in content

    # Answering everything at once reaches the result
    data.update(
        {
            "lineaire_total": "5000",
            "transfert_parcelles": "non",
            "meilleur_emplacement": "non",
            MARKER_NAME: "true",
            CHECKBOX_NAME: "on",
        }
    )
    res = client.post(form_url(), data)
    assert res.status_code == 302
    assert res["Location"].startswith("/simulateur/resultat/")


# Checkbox state rules


def test_checkbox_is_never_prefilled_from_the_url(client):
    """Hand-crafted url values must neither pre-check the box nor bind the form."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])
    params = simulation_data(hedges)
    params[CHECKBOX_NAME] = "on"
    params[MARKER_NAME] = "true"

    res = client.get(form_url(params))

    content = res.content.decode()
    tag = checkbox_tag(content)
    assert tag is not None
    assert "checked" not in tag
    assert ACK_ERROR not in content


def test_checkbox_state_is_kept_when_another_field_fails(client):
    """Within a single submission, the checked state survives an error re-render."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[HedgeFactory()])
    # lineaire_total is posted empty: the BCAE8 form is bound and invalid
    data = simulation_data(
        hedges,
        localisation_pac="oui",
        lineaire_total="",
        transfert_parcelles="non",
        meilleur_emplacement="non",
        **{MARKER_NAME: "true", CHECKBOX_NAME: "on"},
    )

    res = client.post(form_url(), data)

    assert res.status_code == 200
    tag = checkbox_tag(res.content.decode())
    assert tag is not None
    assert "checked" in tag


# Motif-dependent message


def test_all_motif_variants_are_rendered_but_only_the_selected_one_shows(client):
    """Every variant is in the page so JS can swap them without a round-trip."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])

    res = client.get(form_url(simulation_data(hedges, motif="securite")))

    content = res.content.decode()
    for motif in ALL_MOTIFS:
        tag = motif_variant_tag(content, motif)
        assert tag is not None, f"missing message variant for motif {motif}"
        if motif == "securite":
            assert "hidden" not in tag
        else:
            assert "hidden" in tag


# Result pages are never gated


def test_result_page_is_not_gated(client):
    """The result page re-validates url data but never requires the checkbox."""
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])
    url = reverse("moulinette_result")

    res = client.get(f"{url}?{urlencode(simulation_data(hedges))}")

    assert res.status_code == 200


@patch("envergo.hedges.services.get_replantation_coefficient_by_category")
def test_result_plantation_page_is_not_gated(mock_R, client):
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])
    url = reverse("moulinette_result_plantation")
    mock_R.return_value = {HedgeCategory.hru: decimal.Decimal(0.0)}

    res = client.get(f"{url}?{urlencode(simulation_data(hedges))}")

    assert res.status_code == 200


# Kill switch


def test_kill_switch_disables_the_feature(client, settings):
    """Disabling the setting removes both the block and the submission gate."""
    settings.HAIE_EVITER_REDUIRE_ENABLED = False
    DCConfigHaieFactory()
    hedges = HedgeDataFactory(hedges=[ru_hedge()])

    res = client.get(form_url(simulation_data(hedges)))
    assert BLOCK_TITLE not in res.content.decode()

    res = client.post(form_url(), simulation_data(hedges))
    assert res.status_code == 302
    assert res["Location"].startswith("/simulateur/resultat/")
