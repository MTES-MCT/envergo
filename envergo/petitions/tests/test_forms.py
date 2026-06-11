from envergo.moulinette.regulations import HedgeCategory
from envergo.petitions.forms import PetitionProjectForm


class TestPetitionProjectFormCleanCategory:

    def test_valid_category_ru(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "Régime unique",
            }
        )
        form.is_valid()
        assert form.cleaned_data["_category"] == HedgeCategory.ru

    def test_valid_category_hru(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "Hors régime unique",
            }
        )
        form.is_valid()
        assert form.cleaned_data["_category"] == HedgeCategory.hru

    def test_valid_category_l350_3(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "L350-3",
            }
        )
        form.is_valid()
        assert form.cleaned_data["_category"] == HedgeCategory.l350_3

    def test_invalid_category_raises_error(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "invalid_value",
            }
        )
        assert not form.is_valid()
        assert "_category" in form.errors

    def test_empty_category_raises_error(self):
        form = PetitionProjectForm(
            data={
                "moulinette_url": "http://haie.local/simulateur/resultat/?department=44",
                "_category": "",
            }
        )
        assert not form.is_valid()
        assert "_category" in form.errors
