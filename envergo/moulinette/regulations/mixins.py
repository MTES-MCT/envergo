from envergo.moulinette.regulations import TO_ADD, ActionsToTakeMixin


class ZoneHumideMixin(ActionsToTakeMixin):

    ACTIONS_TO_TAKE_MATRIX = {"action_requise": {TO_ADD: {"etude_zh"}}}

    def get_catalog_data(self):
        data = {}
        if "wetlands_25" not in self.catalog:
            data["wetlands_25"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= 25
            ]
            data["wetlands_within_25m"] = bool(data["wetlands_25"])

        if "wetlands_100" not in self.catalog:
            data["wetlands_100"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= 100
            ]
            data["wetlands_within_100m"] = bool(data["wetlands_100"])

        if "potential_wetlands_10" not in self.catalog:
            data["potential_wetlands_10"] = [
                zone
                for zone in self.catalog["potential_wetlands"]
                if zone.distance <= 10
            ]
            data["potential_wetlands_within_10m"] = bool(data["potential_wetlands_10"])

        if "forbidden_wetlands_25" not in self.catalog:
            data["forbidden_wetlands_25"] = [
                zone
                for zone in self.catalog["forbidden_wetlands"]
                if zone.distance <= 25
            ]
            data["forbidden_wetlands_within_25m"] = bool(data["forbidden_wetlands_25"])

        if "forbidden_wetlands_100" not in self.catalog:
            data["forbidden_wetlands_100"] = [
                zone
                for zone in self.catalog["forbidden_wetlands"]
                if zone.distance <= 100
            ]
            data["forbidden_wetlands_within_100m"] = bool(
                data["forbidden_wetlands_100"]
            )

        if "within_potential_wetlands_department" not in self.catalog:
            if self.moulinette.config:
                data["within_potential_wetlands_department"] = (
                    self.moulinette.config.zh_doubt
                )
            else:
                data["within_potential_wetlands_department"] = False

        return data


class ZoneInondableMixin:
    def get_catalog_data(self):
        data = super().get_catalog_data()

        if "flood_zones_12" not in self.catalog:
            data["flood_zones_12"] = [
                zone for zone in self.catalog["flood_zones"] if zone.distance <= 12
            ]
            data["flood_zones_within_12m"] = bool(data["flood_zones_12"])

        if "potential_flood_zones_0" not in self.catalog:
            data["potential_flood_zones_0"] = [
                zone
                for zone in self.catalog["potential_flood_zones"]
                if zone.distance <= 0
            ]
            data["potential_flood_zones_within_0m"] = bool(
                data["potential_flood_zones_0"]
            )

        return data
