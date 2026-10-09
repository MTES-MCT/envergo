import pytest

from envergo.hedges.forms import (
    HedgePropertiesBaseForm,
    HedgeToPlantPropertiesCalvadosForm,
    HedgeToRemovePropertiesRegimeUniqueForm,
)
from envergo.moulinette.forms.fields import DisplayChoiceField


def all_subclasses(cls):
    for subclass in cls.__subclasses__():
        yield subclass
        yield from all_subclasses(subclass)


def test_display_choices_use_the_display_value():
    form = HedgeToPlantPropertiesCalvadosForm(single_procedure=True)
    assert form.fields["mode_plantation"].display_choices == [
        ("plantation", "Plantation nouvelle ou remplacement"),
        ("renforcement", "Renforcement d'une haie existante"),
        ("reconnexion", "Reconnexion d'une haie discontinue"),
    ]

    form = HedgeToRemovePropertiesRegimeUniqueForm(single_procedure=True)
    assert (
        "coupe_a_blanc",
        "Coupe à blanc (sur essence ne recépant pas)",
    ) in form.fields["mode_destruction"].display_choices


@pytest.mark.parametrize(
    "form_class",
    sorted(all_subclasses(HedgePropertiesBaseForm), key=lambda c: c.__name__),
)
@pytest.mark.parametrize("single_procedure", [True, False])
def test_read_only_labels_have_no_html(form_class, single_procedure):
    """Fields with a hint in their label must be Display*Field with a display label.

    Otherwise the html is displayed as is in the read only dialog."""
    form = form_class(single_procedure=single_procedure)
    for name, field in form.fields.items():
        if name == "type_haie":
            continue

        label = getattr(field, "display_label", None) or field.label
        assert label, name
        assert "<" not in label, name

        if hasattr(field, "choices"):
            assert isinstance(field, DisplayChoiceField), name
            for _, choice_label in field.display_choices:
                assert "<" not in choice_label, name

    for _, label in form.fields["type_haie"].choices:
        assert "<" not in label
