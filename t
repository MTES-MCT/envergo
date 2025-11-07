[1mdiff --git i/envergo/petitions/models.py w/envergo/petitions/models.py[m
[1mindex ae3aa6a1..38734cfb 100644[m
[1m--- i/envergo/petitions/models.py[m
[1m+++ w/envergo/petitions/models.py[m
[36m@@ -1,6 +1,7 @@[m
 import logging[m
 import secrets[m
 from datetime import datetime, timedelta[m
[32m+[m[32mfrom functools import cache[m
 from urllib.parse import urlparse[m
 [m
 from dateutil import parser[m
[36m@@ -307,11 +308,12 @@[m [mclass PetitionProject(models.Model):[m
 [m
     def get_moulinette(self):[m
         """Recreate moulinette from moulinette url and hedge data"""[m
[31m-        moulinette_data = self._parse_moulinette_data()[m
[31m-        moulinette_data["haies"] = self.hedge_data[m
[31m-        form_data = {"initial": moulinette_data, "data": moulinette_data}[m
[31m-        moulinette = MoulinetteHaie(form_data)[m
[31m-        return moulinette[m
[32m+[m[32m        if not hasattr(self, "_moulinette"):[m
[32m+[m[32m            moulinette_data = self._parse_moulinette_data()[m
[32m+[m[32m            moulinette_data["haies"] = self.hedge_data[m
[32m+[m[32m            form_data = {"initial": moulinette_data, "data": moulinette_data}[m
[32m+[m[32m            self._moulinette = MoulinetteHaie(form_data)[m
[32m+[m[32m        return self._moulinette[m
 [m
     def get_triage_form(self):[m
         """Recreate triage form from moulinette url"""[m
