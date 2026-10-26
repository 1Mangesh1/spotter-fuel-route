import io
import json
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.test import SimpleTestCase

from planner.routing import NoRouteFound, RoutingError, get_route

CHICAGO = (41.837, -87.685)
DENVER = (39.762, -104.876)


def osrm_body(coordinates, duration_s=7200.0):
    body = {
        "code": "Ok",
        "routes": [{"duration": duration_s, "geometry": {"coordinates": coordinates}}],
    }
    return io.BytesIO(json.dumps(body).encode())


def http_error(status, code):
    body = io.BytesIO(json.dumps({"code": code}).encode())
    return HTTPError("https://osrm.test", status, "error", {}, body)


class GetRouteTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("planner.routing.urlopen")
    def test_reads_points_distance_and_duration(self, urlopen):
        urlopen.return_value = osrm_body([[-100.0, 40.0], [-99.0, 40.0]])
        route = get_route(CHICAGO, DENVER)
        self.assertEqual(route.points, [(40.0, -100.0), (40.0, -99.0)])
        self.assertAlmostEqual(route.distance_miles, 52.93, delta=0.05)
        self.assertEqual(route.duration_hours, 2.0)

    @patch("planner.routing.urlopen")
    def test_sends_one_request_per_start_and_finish(self, urlopen):
        urlopen.side_effect = lambda *args, **kwargs: osrm_body([[-100.0, 40.0], [-99.0, 40.0]])
        get_route(CHICAGO, DENVER)
        get_route(CHICAGO, DENVER)
        self.assertEqual(urlopen.call_count, 1)
        url = urlopen.call_args.args[0].full_url
        self.assertIn("/route/v1/driving/-87.685,41.837;-104.876,39.762?", url)

    @patch("planner.routing.urlopen")
    def test_no_road_between_the_points(self, urlopen):
        urlopen.side_effect = http_error(400, "NoRoute")
        with self.assertRaises(NoRouteFound):
            get_route(CHICAGO, DENVER)

    @patch("planner.routing.urlopen", side_effect=URLError("connection refused"))
    def test_service_down(self, urlopen):
        with self.assertRaisesMessage(RoutingError, "routing service"):
            get_route(CHICAGO, DENVER)
