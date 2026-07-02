from unittest.mock import patch

import pytest
import requests

from envergo.evaluations.tasks import (
    post_a_model_to_automation,
    post_evalreq_to_automation,
    post_evaluation_to_automation,
)
from envergo.evaluations.tests.factories import RequestFactory, RequestFileFactory

pytestmark = pytest.mark.django_db


# Let's make sure the webhook url is defined
@pytest.fixture(autouse=True)
def setup_make_com_webhook(settings):
    settings.MAKE_COM_WEBHOOK = "https://example.com/dummy-webhook/"


@patch("envergo.evaluations.tasks.post")
def test_request_history_first_request(mock_post):
    """The request history is added to the make.com payload."""

    evalreq = RequestFactory(
        user_type="instructor", urbanism_department_emails=["instructor1@example.com"]
    )
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "request_history" in payload
    assert "instructor1@example.com" in payload["request_history"]

    # There is no previous request, so the history is zero
    assert payload["request_history"]["instructor1@example.com"] == 0


@patch("envergo.evaluations.tasks.post")
def test_request_files(mock_post):
    """The request files are joined to the payload."""

    evalreq = RequestFactory(
        user_type="instructor", urbanism_department_emails=["instructor1@example.com"]
    )
    RequestFileFactory(request=evalreq)
    RequestFileFactory(request=evalreq)
    RequestFileFactory(request=evalreq)
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "files" in payload
    assert len(payload["files"]) == 3


@patch("envergo.evaluations.tasks.post")
def test_request_history_first_request_several_emails(mock_post):
    """The request history is added for every email."""

    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor2@example.com",
            "instructor3@example.com",
        ],
    )
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "request_history" in payload
    assert "instructor1@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor1@example.com"] == 0

    assert "instructor2@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor2@example.com"] == 0

    assert "instructor3@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor3@example.com"] == 0


@patch("envergo.evaluations.tasks.post")
def test_request_history_many_requests(mock_post):
    """The request history counts the number of previous requests."""

    RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
        ],
    )
    RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor2@example.com",
        ],
    )
    RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor3@example.com",
        ],
    )
    RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor2@example.com",
        ],
    )
    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor2@example.com",
            "instructor3@example.com",
        ],
    )
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "request_history" in payload
    assert "instructor1@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor1@example.com"] == 3

    assert "instructor2@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor2@example.com"] == 2

    assert "instructor3@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor3@example.com"] == 1


@patch("envergo.evaluations.tasks.post")
def test_request_history_many_requests_some_emails(mock_post):
    """The request history only features emails in the current request."""

    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
        ],
    )
    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor2@example.com",
        ],
    )
    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor3@example.com",
        ],
    )
    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor2@example.com",
        ],
    )
    evalreq = RequestFactory(
        user_type="instructor",
        urbanism_department_emails=[
            "instructor1@example.com",
            "instructor2@example.com",
        ],
    )
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "request_history" in payload
    assert "instructor1@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor1@example.com"] == 3

    assert "instructor2@example.com" in payload["request_history"]
    assert payload["request_history"]["instructor2@example.com"] == 2

    assert "instructor3@example.com" not in payload["request_history"]


@patch("envergo.evaluations.tasks.post")
def test_request_history_petitioner(mock_post):
    """The request history is only added for instructor requests."""

    evalreq = RequestFactory(user_type="petitioner")
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    mock_post.assert_called_once()
    payload = mock_post.call_args.kwargs["json"]
    assert "request_history" not in payload


@patch("envergo.evaluations.tasks.post")
def test_make_com_post_uses_timeout(mock_post, settings):
    """The webhook POST always passes a timeout, so a hung make.com cannot
    block the worker indefinitely."""

    mock_post.return_value.status_code = 200
    evalreq = RequestFactory(user_type="petitioner")
    post_evalreq_to_automation(evalreq.id, "envergo.local")

    assert mock_post.call_args.kwargs["timeout"] == settings.DEFAULT_HTTP_TIMEOUT


@patch("envergo.evaluations.tasks.post")
def test_make_com_post_raises_on_http_error(mock_post):
    """A failing webhook response propagates, so the task's retry policy kicks
    in instead of silently dropping the payload."""

    mock_post.return_value.status_code = 500
    mock_post.return_value.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "boom"
    )
    evalreq = RequestFactory(user_type="petitioner")

    with pytest.raises(requests.exceptions.HTTPError):
        post_a_model_to_automation(evalreq, "https://example.com/dummy-webhook/")


@pytest.mark.parametrize(
    "task", [post_evalreq_to_automation, post_evaluation_to_automation]
)
def test_automation_tasks_retry_by_default(task):
    """The shared base task makes outbound tasks retry on any failure."""

    assert task.autoretry_for == (Exception,)
    assert task.max_retries == 5
