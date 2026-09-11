from envergo.moulinette.regulations import TO_ADD, ActionsToTakeMixin


def within(zones, distance):
    """Whether at least one of the zones is within `distance` meters of the project."""
    return any(zone.distance <= distance for zone in zones)


class ZoneHumideMixin(ActionsToTakeMixin):

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": {TO_ADD: {"etude_zh"}}}

    def get_catalog_data(self):
        data = super().get_catalog_data()

        facts = {
            "wetlands_within_25m": ("wetlands", 25),
            "wetlands_within_100m": ("wetlands", 100),
            "potential_wetlands_within_10m": ("potential_wetlands", 10),
            "forbidden_wetlands_within_25m": ("forbidden_wetlands", 25),
            "forbidden_wetlands_within_100m": ("forbidden_wetlands", 100),
        }
        for key, (zones_key, distance) in facts.items():
            if key not in self.catalog:
                data[key] = within(self.catalog[zones_key], distance)

        if "within_potential_wetlands_department" not in self.catalog:
            config = self.moulinette.config
            data["within_potential_wetlands_department"] = bool(
                config and config.zh_doubt
            )

        return data


class ZoneInondableMixin:
    def get_catalog_data(self):
        data = super().get_catalog_data()

        facts = {
            "flood_zones_within_12m": ("flood_zones", 12),
            "potential_flood_zones_within_0m": ("potential_flood_zones", 0),
        }
        for key, (zones_key, distance) in facts.items():
            if key not in self.catalog:
                data[key] = within(self.catalog[zones_key], distance)

        return data
