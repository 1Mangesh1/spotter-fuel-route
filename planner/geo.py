"""Great-circle distance helpers. Points are (latitude, longitude) in degrees."""

from collections.abc import Sequence
from itertools import pairwise
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_MILES = 3958.7613

type LatLon = tuple[float, float]


def haversine_miles(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * asin(sqrt(h))


def cumulative_miles(points: Sequence[LatLon]) -> list[float]:
    """Distance from the first point to each point, following the polyline."""
    totals = [0.0]
    for a, b in pairwise(points):
        totals.append(totals[-1] + haversine_miles(a, b))
    return totals


def sample_indices(cum_miles: Sequence[float], spacing: float) -> list[int]:
    """Indices of about one point per `spacing` miles. The first and last points are kept."""
    kept = [0]
    for i in range(1, len(cum_miles) - 1):
        if cum_miles[i] - cum_miles[kept[-1]] >= spacing:
            kept.append(i)
    if len(cum_miles) > 1:
        kept.append(len(cum_miles) - 1)
    return kept
