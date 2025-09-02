from envergo.moulinette.templatetags.moulinette import humanize_motif


def test_display_choice():
    result = humanize_motif("amelioration_culture")
    assert "Amélioration des conditions d’exploitation agricole" in result
