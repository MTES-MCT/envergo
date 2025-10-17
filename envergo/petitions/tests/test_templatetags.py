from datetime import datetime

from envergo.petitions.templatetags.petitions import display_due_date


def test_display_choice():
    today = datetime.now()

    ten_days_ago = today.replace(day=today.day - 10).date()
    one_day_ago = today.replace(day=today.day - 1).date()
    in_one_day = today.replace(day=today.day + 1).date()
    in_five_days = today.replace(day=today.day + 5).date()
    in_ten_days = today.replace(day=today.day + 10).date()

    result = display_due_date(in_ten_days)
    assert "fr-icon-timer-line" in result
    assert "10 jours restants" in result

    result = display_due_date(in_five_days)
    assert "fr-icon-hourglass-2-fill" in result
    assert "5 jours restants" in result

    result = display_due_date(in_one_day)
    assert "fr-icon-hourglass-2-fill" in result
    assert "1 jour restant" in result

    result = display_due_date(today.date())
    assert "fr-icon-hourglass-2-fill" in result
    assert "0 jour restant" in result

    result = display_due_date(one_day_ago)
    assert "fr-icon-warning-fill" in result
    assert "Dépassée depuis 1 jour" in result

    result = display_due_date(ten_days_ago)
    assert "fr-icon-warning-fill" in result
    assert "Dépassée depuis 10 jours" in result
