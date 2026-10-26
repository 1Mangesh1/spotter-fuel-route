import io
import json
from unittest.mock import patch
from urllib.error import URLError

from django.core.cache import cache
from django.test import TestCase

from planner.models import FuelStation
from planner.stations import get_station_index

URL = "/api/route/"
START, FINISH = "30.0,-100.0", "34.0,-100.0"


def meridian_route(*args, **kwargs):
    """A straight 4-degree road north along longitude -100: 276.37 miles."""
    coordinates = [[-100.0, 30.0 + i / 100] for i in range(401)]
    body = {
        "code": "Ok",
        "routes": [{"duration": 18000.0, "geometry": {"coordinates": coordinates}}],
    }
    return io.BytesIO(json.dumps(body).encode())


def add_station(opis_id, name, lat, lon, price):
    FuelStation.objects.create(
        opis_id=opis_id,
        name=name,
        address="I-27, EXIT 1",
        city="Town",
        state="TX",
        price=price,
        lat=lat,
        lon=lon,
    )


@patch("planner.routing.urlopen", side_effect=meridian_route)
class RoutePlanApiTests(TestCase):
    def setUp(self):
        cache.clear()
        get_station_index.cache_clear()
        add_station(1, "Start Stop", 30.0, -100.01, "4.000")
        add_station(2, "Cheap Stop", 32.0, -100.01, "3.000")
        add_station(3, "Far Away Stop", 32.0, -98.0, "1.000")

    def test_empty_tank_plan(self, urlopen):
        response = self.client.get(URL, {"start": START, "finish": FINISH})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["start_tank"], "empty")
        self.assertEqual(data["distance_miles"], 276.4)
        self.assertEqual(data["duration_hours"], 5.0)
        self.assertEqual([s["name"] for s in data["fuel_stops"]], ["Start Stop", "Cheap Stop"])
        self.assertEqual(data["fuel_stops"][0]["gallons"], 13.82)
        self.assertEqual(data["fuel_stops"][0]["cost"], 55.27)
        self.assertEqual(data["fuel_stops"][1]["mile_marker"], 138.2)
        self.assertEqual(data["fuel_stops"][1]["cost"], 41.46)
        self.assertEqual(data["total_gallons"], 27.64)
        self.assertEqual(data["total_fuel_cost"], 96.73)
        self.assertEqual(data["route_geometry"]["type"], "LineString")
        self.assertIn("start=30.0%2C-100.0", data["map_url"])

    def test_full_tank_needs_no_stop_for_a_short_trip(self, urlopen):
        response = self.client.get(URL, {"start": START, "finish": FINISH, "start_tank": "full"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["fuel_stops"], [])
        self.assertEqual(response.json()["total_fuel_cost"], 0)

    def test_unknown_place_is_a_bad_request(self, urlopen):
        response = self.client.get(URL, {"start": "Atlantis, IL", "finish": FINISH})
        self.assertEqual(response.status_code, 400)
        self.assertIn("start", response.json())
        urlopen.assert_not_called()

    def test_missing_finish_is_a_bad_request(self, urlopen):
        response = self.client.get(URL, {"start": START})
        self.assertEqual(response.status_code, 400)
        self.assertIn("finish", response.json())

    def test_no_station_near_the_start(self, urlopen):
        FuelStation.objects.filter(opis_id=1).delete()
        response = self.client.get(URL, {"start": START, "finish": FINISH})
        self.assertEqual(response.status_code, 422)
        self.assertIn("within 10 miles of the start", response.json()["detail"])

    def test_routing_service_down(self, urlopen):
        urlopen.side_effect = URLError("connection refused")
        response = self.client.get(URL, {"start": START, "finish": FINISH})
        self.assertEqual(response.status_code, 502)
