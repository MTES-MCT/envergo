from datetime import timedelta
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.utils import timezone

from envergo.petitions.middleware import HandleInvitationTokenMiddleware
from envergo.petitions.tests.factories import (
    InvitationTokenFactory,
    PetitionProjectFactory,
)
from envergo.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def mock_get_response():
    """Mock the get_response callable for middleware testing."""
    return Mock(return_value=HttpResponse())


@pytest.fixture
def middleware(mock_get_response):
    """Create middleware instance with mock get_response."""
    return HandleInvitationTokenMiddleware(mock_get_response)


@pytest.fixture
def authenticated_user():
    """Create an authenticated user."""
    return UserFactory()


@pytest.fixture
def invitation_creator():
    """Create a user who will create invitations."""
    return UserFactory()


@pytest.fixture
def valid_invitation_token(invitation_creator):
    """Create a valid invitation token."""
    project = PetitionProjectFactory()
    return InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project,
        user=None,  # Not yet accepted
        valid_until=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def expired_invitation_token(invitation_creator):
    """Create an expired invitation token."""
    project = PetitionProjectFactory()
    return InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project,
        user=None,
        valid_until=timezone.now() - timedelta(days=1),
    )


@pytest.fixture
def used_invitation_token(invitation_creator, authenticated_user):
    """Create an already used invitation token."""
    project = PetitionProjectFactory()
    return InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project,
        user=authenticated_user,  # Already accepted
        valid_until=timezone.now() + timedelta(days=30),
    )


def add_messages_middleware(request):
    """Add messages middleware support to request."""
    request.session = SessionStore()
    request._messages = FallbackStorage(request)


def test_no_token_in_url_or_cookie(rf, middleware):
    """Test that middleware does nothing when no token is present."""
    request = rf.get("/")
    request.user = AnonymousUser()
    add_messages_middleware(request)

    response = middleware(request)

    assert response.status_code == 200
    # No cookie should be set
    assert settings.INVITATION_TOKEN_COOKIE_NAME not in response.cookies


def test_unauthenticated_user_with_token_in_url_stores_token(
    rf, middleware, valid_invitation_token
):
    """Test that token is stored in cookie when unauthenticated user has token in URL."""
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_invitation_token.token}"
    request = rf.get(url)
    request.user = AnonymousUser()
    add_messages_middleware(request)

    response = middleware(request)

    # Token should be stored in cookie
    assert settings.INVITATION_TOKEN_COOKIE_NAME in response.cookies
    cookie = response.cookies[settings.INVITATION_TOKEN_COOKIE_NAME]
    assert cookie.value == valid_invitation_token.token
    assert cookie["httponly"] is True

    # User should see a message
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 1
    assert "connectez-vous ou" in str(message_list[0])
    assert "créez un compte" in str(message_list[0])


def test_unauthenticated_user_token_cookie_lifetime(
    rf, middleware, valid_invitation_token
):
    """Test that cookie has correct lifetime (13 months)."""
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_invitation_token.token}"
    request = rf.get(url)
    request.user = AnonymousUser()
    add_messages_middleware(request)

    response = middleware(request)

    cookie = response.cookies[settings.INVITATION_TOKEN_COOKIE_NAME]
    expected_lifetime = timedelta(30 * 13).total_seconds()
    assert cookie["max-age"] == expected_lifetime


def test_authenticated_user_with_token_in_url_processes_token(
    rf, middleware, valid_invitation_token, authenticated_user
):
    """Test that valid token is processed for authenticated user from URL."""
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_invitation_token.token}"
    request = rf.get(url)
    request.user = authenticated_user
    add_messages_middleware(request)

    middleware(request)

    # Token should be accepted
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user == authenticated_user

    # User should see success message
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 1
    assert "dossier a été rattaché" in str(message_list[0])


def test_authenticated_user_with_token_in_cookie_processes_token(
    rf, middleware, valid_invitation_token, authenticated_user
):
    """Test that valid token is processed for authenticated user from cookie."""
    request = rf.get("/")
    request.user = authenticated_user
    request.COOKIES = {
        settings.INVITATION_TOKEN_COOKIE_NAME: valid_invitation_token.token
    }
    add_messages_middleware(request)

    middleware(request)

    # Token should be accepted
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user == authenticated_user

    # User should see success message
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 1
    assert "dossier a été rattaché" in str(message_list[0])


def test_authenticated_user_cookie_cleared_after_processing(
    rf, middleware, valid_invitation_token, authenticated_user
):
    """Test that cookie is deleted after processing for authenticated user."""
    request = rf.get("/")
    request.user = authenticated_user
    request.COOKIES = {
        settings.INVITATION_TOKEN_COOKIE_NAME: valid_invitation_token.token
    }
    add_messages_middleware(request)

    response = middleware(request)

    # Cookie should be deleted
    assert settings.INVITATION_TOKEN_COOKIE_NAME in response.cookies
    # Django sets max_age=0 to delete cookies
    assert response.cookies[settings.INVITATION_TOKEN_COOKIE_NAME]["max-age"] == 0


def test_expired_token_shows_warning(
    rf, middleware, expired_invitation_token, authenticated_user
):
    """Test that expired token shows warning message."""
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={expired_invitation_token.token}"
    request = rf.get(url)
    request.user = authenticated_user
    add_messages_middleware(request)

    middleware(request)

    # Token should NOT be accepted
    expired_invitation_token.refresh_from_db()
    assert expired_invitation_token.user is None

    # User should see warning message
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 1
    assert message_list[0].level == messages.WARNING
    assert "n'est plus valide" in str(message_list[0])


def test_used_token_shows_warning(
    rf, middleware, used_invitation_token, invitation_creator
):
    """Test that already used token shows warning message."""
    # Try to use the token with a different user
    another_user = UserFactory()
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={used_invitation_token.token}"
    request = rf.get(url)
    request.user = another_user
    add_messages_middleware(request)

    middleware(request)

    # Token should NOT be reassigned
    used_invitation_token.refresh_from_db()
    assert used_invitation_token.user != another_user

    # User should see warning message
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 1
    assert message_list[0].level == messages.WARNING
    assert "n'est plus valide" in str(message_list[0])


def test_creator_cannot_use_own_token(rf, middleware, valid_invitation_token):
    """Test that token creator cannot accept their own invitation."""
    creator = valid_invitation_token.created_by
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_invitation_token.token}"
    request = rf.get(url)
    request.user = creator
    add_messages_middleware(request)

    middleware(request)

    # Token should NOT be accepted by creator
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user != creator
    assert valid_invitation_token.user is None

    # User should see warning message
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 1
    assert message_list[0].level == messages.WARNING


def test_nonexistent_token_no_error(rf, middleware, authenticated_user):
    """Test that non-existent token doesn't cause errors."""
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}=nonexistent_token_123"
    request = rf.get(url)
    request.user = authenticated_user
    add_messages_middleware(request)

    response = middleware(request)

    # Should not raise error and no messages
    assert response.status_code == 200
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 0


def test_both_url_and_cookie_token_processes_both(
    rf, middleware, invitation_creator, authenticated_user
):
    """Test that both URL and cookie tokens are processed."""
    # Create two different valid tokens
    project1 = PetitionProjectFactory(reference="ABC125")
    project2 = PetitionProjectFactory(reference="ABC126")
    token1 = InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project1,
        user=None,
        valid_until=timezone.now() + timedelta(days=30),
    )
    token2 = InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project2,
        user=None,
        valid_until=timezone.now() + timedelta(days=30),
    )

    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={token1.token}"
    request = rf.get(url)
    request.user = authenticated_user
    request.COOKIES = {settings.INVITATION_TOKEN_COOKIE_NAME: token2.token}
    add_messages_middleware(request)

    middleware(request)

    # Both tokens should be accepted
    token1.refresh_from_db()
    token2.refresh_from_db()
    assert token1.user == authenticated_user
    assert token2.user == authenticated_user

    # User should see success messages (one for each token)
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 2


def test_unauthenticated_user_does_not_process_token_in_cookie(
    rf, middleware, valid_invitation_token
):
    """Test that unauthenticated user with cookie doesn't process it."""
    request = rf.get("/")
    request.user = AnonymousUser()
    request.COOKIES = {
        settings.INVITATION_TOKEN_COOKIE_NAME: valid_invitation_token.token
    }
    add_messages_middleware(request)

    middleware(request)

    # Token should NOT be processed
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user is None

    # No messages should be shown (token will be processed after login)
    message_list = list(messages.get_messages(request))
    assert len(message_list) == 0


def test_token_stored_for_later_processing_workflow(
    rf, middleware, valid_invitation_token, authenticated_user
):
    """Test complete workflow: anonymous user clicks link, then logs in."""
    # Step 1: Anonymous user clicks invitation link
    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_invitation_token.token}"
    request1 = rf.get(url)
    request1.user = AnonymousUser()
    add_messages_middleware(request1)

    response1 = middleware(request1)

    # Token stored in cookie
    assert settings.INVITATION_TOKEN_COOKIE_NAME in response1.cookies
    cookie_value = response1.cookies[settings.INVITATION_TOKEN_COOKIE_NAME].value

    # Token not yet processed
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user is None

    # Step 2: User logs in and makes another request with the cookie
    request2 = rf.get("/")
    request2.user = authenticated_user
    request2.COOKIES = {settings.INVITATION_TOKEN_COOKIE_NAME: cookie_value}
    add_messages_middleware(request2)

    response2 = middleware(request2)

    # Token should now be processed
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user == authenticated_user

    # Cookie should be cleared
    assert response2.cookies[settings.INVITATION_TOKEN_COOKIE_NAME]["max-age"] == 0


def test_invitation_token_model_is_valid_method(db, invitation_creator):
    """Test the is_valid method on InvitationToken model."""
    project = PetitionProjectFactory()
    user = UserFactory()

    # Valid token
    valid_token = InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project,
        user=None,
        valid_until=timezone.now() + timedelta(days=30),
    )
    assert valid_token.is_valid(user) is True

    # Invalid: already used
    used_token = InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project,
        user=user,
        valid_until=timezone.now() + timedelta(days=30),
    )
    another_user = UserFactory()
    assert used_token.is_valid(another_user) is False

    # Invalid: creator trying to use own token
    assert valid_token.is_valid(invitation_creator) is False

    # Invalid: expired
    expired_token = InvitationTokenFactory(
        created_by=invitation_creator,
        petition_project=project,
        user=None,
        valid_until=timezone.now() - timedelta(days=1),
    )
    assert expired_token.is_valid(user) is False


def test_middleware_processes_request_before_response(
    rf,
    mock_get_response,
    valid_invitation_token,
    authenticated_user,
):
    """Test that token is processed before response is generated (prevents 403)."""
    middleware = HandleInvitationTokenMiddleware(mock_get_response)

    url = f"/?{settings.INVITATION_TOKEN_COOKIE_NAME}={valid_invitation_token.token}"
    request = rf.get(url)
    request.user = authenticated_user
    add_messages_middleware(request)

    # Call the middleware
    middleware(request)

    # Verify that get_response was called
    mock_get_response.assert_called_once_with(request)

    # Verify token was processed (invitation accepted)
    valid_invitation_token.refresh_from_db()
    assert valid_invitation_token.user == authenticated_user
