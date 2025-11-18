from envergo.utils.templatetags.utils import urlize_html


def test_urlize_html():
    """Test urlize_html filter"""
    expected_result = 'voici un lien <a target="_blank" href="https://exemple.com" rel="nofollow">https://exemple.com</a>'  # noqa

    # Given a text message with a link
    message = "voici un lien https://exemple.com"
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result

    # Given a html message with a link
    message = 'voici un lien <a href="https://exemple.com" rel="nofollow">https://exemple.com</a>'
    # When message is urlized
    result = urlize_html(message)
    # Then result is expected_result
    assert result == expected_result
