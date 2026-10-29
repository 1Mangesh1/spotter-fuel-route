import csv
import tempfile
import zipfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

PLACES = """\
USPS|GEOID|GEOIDFQ|ANSICODE|NAME|LSAD|FUNCSTAT|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG
ID|1600001|x|x|Boise City city|25|A|221000000|0|0|0|43.59805|-116.231596
NJ|3400001|x|x|Fairview borough|21|A|2000|0|0|0|40.81|-73.99
OK|4000001|x|x|Boise City city|25|A|4000000|0|0|0|36.731336|-102.509522
"""
COUSUBS = """\
USPS|GEOID|GEOIDFQ|ANSICODE|NAME|FUNCSTAT|ALAND|AWATER|ALAND_SQMI|AWATER_SQMI|INTPTLAT|INTPTLONG
NJ|3400300001|x|x|Mahwah township|A|67000000|0|0|0|41.09|-74.19
NJ|3400300002|x|x|Fairview township|A|9000000|0|0|0|39.50|-75.10
NJ|3400300003|x|x|Franklin township|A|1000|0|0|0|40.00|-74.00
NJ|3400300004|x|x|Franklin township|A|2000|0|0|0|41.00|-75.00
"""


def write_zip(folder: Path, name: str, text: str) -> Path:
    path = folder / f"{name}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{name}.txt", text)
    return path


class BuildPlacesTests(SimpleTestCase):
    def build(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            out_csv = folder / "us_places.csv"
            places = write_zip(folder, "places", PLACES)
            cousubs = write_zip(folder, "cousubs", COUSUBS)
            with patch("planner.management.commands.build_places.PLACES_CSV", out_csv):
                call_command("build_places", places, "--cousubs", cousubs, stdout=StringIO())
            with out_csv.open(newline="") as f:
                return {row["name"]: row for row in csv.DictReader(f)}

    def test_adds_townships_that_are_not_places(self):
        self.assertEqual(self.build()["Mahwah"]["lat"], "41.09")

    def test_a_place_wins_over_a_township_with_the_same_name(self):
        self.assertEqual(self.build()["Fairview"]["lat"], "40.81")

    def test_skips_township_names_that_repeat_in_a_state(self):
        self.assertNotIn("Franklin", self.build())

    def test_boise_city_is_also_boise_in_idaho_only(self):
        self.assertEqual(
            self.build()["Boise"],
            {"name": "Boise", "state": "ID", "lat": "43.59805", "lon": "-116.231596"},
        )
