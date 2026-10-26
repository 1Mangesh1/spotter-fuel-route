"""Find the fuel stations that are close to a route."""

from collections import defaultdict
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from math import floor

from planner.geo import LatLon, haversine_miles, sample_indices
from planner.models import FuelStation
from planner.optimizer import Candidate

CORRIDOR_MILES = 10
# A 0.5-degree cell is wider than the corridor everywhere in the USA, so the 3x3 cells
# around a point hold every station within the corridor.
_CELL_DEGREES = 0.5
_SAMPLE_SPACING_MILES = 1.0


@dataclass(frozen=True)
class Station:
    id: int
    name: str
    address: str
    city: str
    state: str
    price: float
    lat: float
    lon: float


def _cell(lat: float, lon: float) -> tuple[int, int]:
    return floor(lat / _CELL_DEGREES), floor(lon / _CELL_DEGREES)


class StationIndex:
    """Stations grouped by grid cell, so that a lookup scans only the cells near a point."""

    def __init__(self, stations: Iterable[Station]):
        self._cells: dict[tuple[int, int], list[Station]] = defaultdict(list)
        for s in stations:
            self._cells[_cell(s.lat, s.lon)].append(s)

    def _near(self, point: LatLon) -> Iterator[Station]:
        row, col = _cell(*point)
        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                yield from self._cells.get((row + d_row, col + d_col), ())

    def along_route(
        self,
        points: Sequence[LatLon],
        cum_miles: Sequence[float],
        corridor_miles: float = CORRIDOR_MILES,
    ) -> list[Candidate[Station]]:
        """Stations within `corridor_miles` of the route, at the mile of the closest route point."""
        closest: dict[int, tuple[float, float, Station]] = {}
        for i in sample_indices(cum_miles, _SAMPLE_SPACING_MILES):
            for s in self._near(points[i]):
                offset = haversine_miles(points[i], (s.lat, s.lon))
                if offset <= corridor_miles and (s.id not in closest or offset < closest[s.id][0]):
                    closest[s.id] = (offset, cum_miles[i], s)
        return [Candidate(mile, s.price, s) for _, mile, s in closest.values()]


@cache
def get_station_index() -> StationIndex:
    """Load every station once per process. The import command clears this cache."""
    rows = FuelStation.objects.values(
        "id", "name", "address", "city", "state", "price", "lat", "lon"
    )
    return StationIndex(Station(**{**row, "price": float(row["price"])}) for row in rows)
