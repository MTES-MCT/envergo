from envergo.moulinette.forms.fields import DisplayIntegerField


class TestDisplayIntegerField:
    """Tests for DisplayIntegerField whitespace stripping."""

    def test_strips_regular_spaces(self):
        field = DisplayIntegerField()
        assert field.clean("8 000") == 8000

    def test_strips_multiple_spaces(self):
        field = DisplayIntegerField()
        assert field.clean("1 000 000") == 1000000

    def test_strips_non_breaking_spaces(self):
        field = DisplayIntegerField()
        # \u00a0 is non-breaking space, \u202f is narrow non-breaking space
        assert field.clean("8\u00a0000") == 8000
        assert field.clean("8\u202f000") == 8000

    def test_strips_tabs(self):
        field = DisplayIntegerField()
        assert field.clean("8\t000") == 8000

    def test_handles_normal_integer(self):
        field = DisplayIntegerField()
        assert field.clean("8000") == 8000

    def test_handles_integer_value(self):
        field = DisplayIntegerField()
        assert field.clean(8000) == 8000

    def test_handles_empty_value(self):
        field = DisplayIntegerField(required=False)
        assert field.clean("") is None
