from django.test import SimpleTestCase

from planner.geo import cumulative_miles
from planner.stations import Station, StationIndex


def station(station_id, lat, lon, price=3.5):
    return Station(station_id, f"Stop {station_id}", "I-80 Exit 1", "Town", "NE", price, lat, lon)


class AlongRouteTests(SimpleTestCase):
    def setUp(self):
        # A straight road along latitude 40, from longitude -100 to -95.
        self.points = [(40.0, -100.0 + i / 100) for i in range(501)]
        self.cum = cumulative_miles(self.points)

    def test_keeps_stations_inside_the_corridor_at_their_mile_marker(self):
        index = StationIndex([station(1, 40.05, -98.0)])
        [candidate] = index.along_route(self.points, self.cum)
        self.assertEqual(candidate.station.id, 1)
        self.assertEqual(candidate.price, 3.5)
        # 2 degrees of longitude at latitude 40 is 105.86 miles.
        self.assertAlmostEqual(candidate.mile, 105.86, delta=1.0)

    def test_skips_stations_far_from_the_route(self):
        index = StationIndex([station(2, 40.5, -97.0), station(3, 40.0, -90.0)])
        self.assertEqual(index.along_route(self.points, self.cum), [])
