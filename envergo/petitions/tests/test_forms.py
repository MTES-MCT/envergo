from envergo.moulinette.regulations import HaieCriterionCategory
from envergo.petitions.forms import PetitionProjectForm


class TestPetitionProjectFormCleanCategory:

    def test_valid_category_ru(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "category": "ru",
            }
        )
        form.is_valid()
        assert form.cleaned_data["category"] == HaieCriterionCategory.ru

    def test_valid_category_hru(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "category": "hru",
            }
        )
        form.is_valid()
        assert form.cleaned_data["category"] == HaieCriterionCategory.hru

    def test_valid_category_l350_3(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "category": "l350_3",
            }
        )
        form.is_valid()
        assert form.cleaned_data["category"] == HaieCriterionCategory.l350_3

    def test_invalid_category_raises_error(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "category": "invalid_value",
            }
        )
        assert not form.is_valid()
        assert "category" in form.errors

    def test_empty_category_raises_error(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "category": "",
            }
        )
        assert not form.is_valid()
        assert "category" in form.errors
