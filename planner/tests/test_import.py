import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from planner.models import FuelStation

CSV = """\
OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price
7,WOODSHED OF BIG CABIN,"I-44, EXIT 283 & US-69",Big Cabin,OK,307,3.00733333
7,WOODSHED OF BIG CABIN,"I-44, EXIT 283 & US-69",Big Cabin,OK,308,2.89900000
9,PILOT TRAVEL CENTER #123,"I-55, EXIT 290",Chicago,IL,101,3.45900000
11,NOWHERE STOP,"US-1, EXIT 1",Atlantis,ZZ,102,3.10000000
"""


class ImportStationsTests(TestCase):
    def run_import(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "prices.csv"
            path.write_text(CSV, encoding="utf-8")
            out = StringIO()
            call_command("import_stations", path, stdout=out)
        return out.getvalue()

    def test_keeps_the_lowest_price_per_station(self):
        self.run_import()
        station = FuelStation.objects.get(opis_id=7)
        self.assertEqual(station.price, Decimal("2.899"))
        self.assertEqual(station.address, "I-44, EXIT 283 & US-69")

    def test_places_stations_at_their_city(self):
        self.run_import()
        station = FuelStation.objects.get(opis_id=9)
        self.assertAlmostEqual(station.lat, 41.837, places=2)
        self.assertAlmostEqual(station.lon, -87.685, places=2)

    def test_reports_stations_without_a_known_city(self):
        output = self.run_import()
        self.assertEqual(FuelStation.objects.count(), 2)
        self.assertIn("Imported 2 stations", output)
        self.assertIn("Skipped 1", output)
        self.assertIn("Atlantis, ZZ", output)

    def test_running_twice_replaces_the_stations(self):
        self.run_import()
        self.run_import()
        self.assertEqual(FuelStation.objects.count(), 2)
