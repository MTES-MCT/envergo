from abc import ABC, abstractmethod
from functools import cached_property

from envergo.evaluations.models import RESULTS


class MoulinetteRegulation(ABC):
    """Run the moulinette for a single regulation (e.g Loi sur l'eau."""

    @cached_property
    def result(self):
        results = [criterion.result for criterion in self.criterions]

        if RESULTS.soumis in results:
            result = RESULTS.soumis
        elif RESULTS.action_requise in results:
            result = RESULTS.action_requise
        else:
            result = RESULTS.non_soumis

        return result

    def body_template(self):
        return f"moulinette/_{self.slug}_{self.result}.html"


class MoulinetteCriterion(ABC):
    """Run a single moulinette check."""

    @cached_property
    @abstractmethod
    def result(self):
        pass


class WaterLaw3310(MoulinetteCriterion):
    slug = "zone-humide"
    title = "Construction en zone humide"


class WaterLaw3220(MoulinetteCriterion):
    slug = "zone-inondable"
    title = "Construction en zone inondable"


class WaterLaw2150(MoulinetteCriterion):
    slug = "ruissellement"
    title = "Imperméabilisation et captation du ruissellement des eaux de pluie"


class WaterLaw(MoulinetteRegulation):
    slug = "loi-sur-leau"
    title = "Loi sur l'eau"
    criterions = [WaterLaw3310(), WaterLaw3220(), WaterLaw2150()]
