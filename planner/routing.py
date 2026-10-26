"""Driving routes from OSRM. Each new start and finish pair costs one HTTP call."""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from planner.geo import LatLon, cumulative_miles

_TIMEOUT_SECONDS = 15
_USER_AGENT = "spotter-fuel-route/1.0"


class RoutingError(Exception):
    """The routing service failed or sent a response that we cannot read."""


class NoRouteFound(RoutingError):
    """The routing service has no road route between the two points."""


@dataclass(frozen=True)
class Route:
    points: list[LatLon]
    cum_miles: list[float]
    duration_hours: float

    @property
    def distance_miles(self) -> float:
        return self.cum_miles[-1]


def get_route(start: LatLon, finish: LatLon) -> Route:
    key = "route:{:.5f},{:.5f}:{:.5f},{:.5f}".format(*start, *finish)
    route = cache.get(key)
    if route is None:
        route = _fetch_route(start, finish)
        cache.set(key, route, settings.ROUTE_CACHE_SECONDS)
    return route


def _fetch_route(start: LatLon, finish: LatLon) -> Route:
    # OSRM takes longitude first.
    coords = f"{start[1]},{start[0]};{finish[1]},{finish[0]}"
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}?overview=full&geometries=geojson"
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            body = json.load(response)
    except HTTPError as exc:
        if _error_code(exc) == "NoRoute":
            raise NoRouteFound("No driving route connects the start and the finish.") from exc
        raise RoutingError(f"The routing service returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RoutingError("The routing service did not respond. Try again later.") from exc

    if body.get("code") != "Ok" or not body.get("routes"):
        raise NoRouteFound("No driving route connects the start and the finish.")
    route = body["routes"][0]
    points = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    return Route(points, cumulative_miles(points), route["duration"] / 3600)


def _error_code(exc: HTTPError) -> str | None:
    try:
        return json.load(exc).get("code")
    except (json.JSONDecodeError, AttributeError):
        return None
