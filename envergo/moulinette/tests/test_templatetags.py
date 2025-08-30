from envergo.moulinette.templatetags.moulinette import display_motif


def test_display_choice():
    result = display_motif("amelioration_culture")
    assert "Amélioration des conditions d’exploitation agricole" in result
