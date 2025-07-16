from envergo.moulinette.regulations import CriterionEvaluator

GEOPORTAIL_URL = "https://www.geoportail-urbanisme.gouv.fr/map/#tile=1&lon=2.424722&lat=46.76305599999998&zoom=6"


class UrbanismeHaie(CriterionEvaluator):
    choice_label = "Urbanisme Haie > Urbanisme Haie"
    slug = "urbanisme_haie"

    def evaluate(self):
        self._result_code, self._result = "a_verifier", "a_verifier"

    def get_catalog_data(self):
        data = super().get_catalog_data()
        geoportail_url = GEOPORTAIL_URL

        if "haies" in self.catalog:
            # Generate a geoportail url centered on the project
            centroid = self.catalog["haies"].get_centroid_to_remove()
            lng = centroid.x
            lat = centroid.y
            zoom = 16
            geoportail_url = f"https://www.geoportail-urbanisme.gouv.fr/map/#tile=1&lon={lng}&lat={lat}&zoom={zoom}&lowscale=0:0.7&municipality=0:0.7&document=0:0.7&zone_secteur,zone_secteur_psmv=0:0.7&du,psmv=1:0.7&info,info_psmv01020304050607080910111213141516171819202122232425262728293031323334353637383940414270979899=0:0.7&info,info_psmv98=0:0.7&info,info_psmv010203040506070809101112131415161718192021222324252627282930313233343536373839404142709799=0:0.7&prescription,prescription_psmv2217233006363743=0:0.7&prescription,prescription_psmv=1:0.7&prescription2217233006363743=0:0.7&prescription_psmv2217233006363743=0:0.7&prescription,prescription_psmv03041115162029383940414445=0:0.7&prescription03041115162029383940414445=0:0.7&prescription_psmv03041115162029383940414445=0:0.7&prescription,prescription_psmv141849=0:0.7&prescription141849=0:0.7&prescription_psmv141849=0:0.7&prescription,prescription_psmv0509102112242627284748=0:0.7&prescription0509102112242627284748=0:0.7&prescription_psmv0509102112242627284748=0:0.7&prescription,prescription_psmv0213195051=0:0.7&prescription0213195051=0:0.7&prescription_psmv0213195051=0:0.7"  # noqa

        data["geoportail_url"] = geoportail_url
        return data
