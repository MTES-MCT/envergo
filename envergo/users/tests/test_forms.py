from envergo.users.forms import RegisterForm
from envergo.users.tests.utils import signed_display_time


def test_human_submission_is_not_a_bot():
    form = RegisterForm(data={"displayed_at": signed_display_time(10)})
    assert not form.is_bot_submission()


def test_filled_honeypot_is_a_bot():
    form = RegisterForm(
        data={"displayed_at": signed_display_time(10), "website": "spam.example"}
    )
    assert form.is_bot_submission()


def test_fast_submission_is_a_bot():
    form = RegisterForm(data={"displayed_at": signed_display_time(2)})
    assert form.is_bot_submission()


def test_tampered_display_time_is_a_bot():
    tampered = signed_display_time(10) + "x"
    form = RegisterForm(data={"displayed_at": tampered})
    assert form.is_bot_submission()


def test_missing_display_time_is_a_bot():
    form = RegisterForm(data={})
    assert form.is_bot_submission()
