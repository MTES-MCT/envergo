from django.contrib.gis.measure import Distance as D


class ZoneHumideMixin:
    def get_catalog_data(self):
        data = {}

        if "wetlands_25" not in self.catalog:
            data["wetlands_25"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=25)
            ]
            data["wetlands_within_25m"] = bool(data["wetlands_25"])

        if "wetlands_100" not in self.catalog:
            data["wetlands_100"] = [
                zone for zone in self.catalog["wetlands"] if zone.distance <= D(m=100)
            ]
            data["wetlands_within_100m"] = bool(data["wetlands_100"])

        if "potential_wetlands_0" not in self.catalog:
            data["potential_wetlands_0"] = [
                zone
                for zone in self.catalog["potential_wetlands"]
                if zone.distance <= D(m=0)
            ]
            data["potential_wetlands_within_0m"] = bool(data["potential_wetlands_0"])

        if "forbidden_wetlands_25" not in self.catalog:
            data["forbidden_wetlands_25"] = [
                zone
                for zone in self.catalog["forbidden_wetlands"]
                if zone.distance <= D(m=25)
            ]
            data["forbidden_wetlands_within_25m"] = bool(data["forbidden_wetlands_25"])

        if "forbidden_wetlands_100" not in self.catalog:
            data["forbidden_wetlands_100"] = [
                zone
                for zone in self.catalog["forbidden_wetlands"]
                if zone.distance <= D(m=100)
            ]
            data["forbidden_wetlands_within_100m"] = bool(
                data["forbidden_wetlands_100"]
            )

        return data
