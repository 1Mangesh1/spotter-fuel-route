"""Choose where to buy fuel along a route so that the trip costs as little as possible.

The route is one line, so a station is a mile marker and a price. The greedy rule below is
optimal for that case: at each station, buy just enough fuel to reach the next cheaper
station in range. If no station in range is cheaper, fill the tank and drive to the cheapest
station in range.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

MAX_RANGE_MILES = 500
MILES_PER_GALLON = 10
START_RADIUS_MILES = 10

_EPSILON = 1e-9


class StartTank(StrEnum):
    EMPTY = "empty"
    FULL = "full"


class NoFeasiblePlan(Exception):
    """The vehicle cannot finish the trip with the stations that are available."""


@dataclass(frozen=True)
class Candidate[T]:
    mile: float
    price: float
    station: T


@dataclass(frozen=True)
class Purchase[T]:
    candidate: Candidate[T]
    gallons: float

    @property
    def cost(self) -> float:
        return self.gallons * self.candidate.price


@dataclass(frozen=True)
class FuelPlan[T]:
    purchases: list[Purchase[T]] = field(default_factory=list)

    @property
    def total_gallons(self) -> float:
        return sum(p.gallons for p in self.purchases)

    @property
    def total_cost(self) -> float:
        return sum(p.cost for p in self.purchases)


def plan_fuel[T](
    candidates: Iterable[Candidate[T]],
    trip_miles: float,
    *,
    start_tank: StartTank = StartTank.EMPTY,
    range_miles: float = MAX_RANGE_MILES,
    mpg: float = MILES_PER_GALLON,
    start_radius_miles: float = START_RADIUS_MILES,
) -> FuelPlan[T]:
    """Return the cheapest set of purchases that gets the vehicle to `trip_miles`.

    EMPTY: the vehicle first fills at the cheapest station within `start_radius_miles` of
    the start. Fuel for those first few miles is paid at that station, so every gallon of
    the trip is paid for. FULL: the vehicle starts with a full tank and pays only for fuel
    bought on the way.
    """
    capacity = range_miles / mpg
    stations = sorted((c for c in candidates if 0 <= c.mile <= trip_miles), key=lambda c: c.mile)

    if start_tank is StartTank.FULL:
        here, here_mile, here_price, fuel, next_index = None, 0.0, math.inf, capacity, 0
    else:
        nearby = [i for i, c in enumerate(stations) if c.mile <= start_radius_miles]
        if not nearby:
            raise NoFeasiblePlan(
                f"No fuel station within {start_radius_miles:g} miles of the start. "
                "Try start_tank=full."
            )
        first = min(nearby, key=lambda i: stations[i].price)
        here = stations[first]
        here_mile, here_price, next_index = here.mile, here.price, first + 1
        fuel = -here.mile / mpg

    purchases: list[Purchase[T]] = []

    def buy(gallons: float) -> float:
        """Buy at the current station. The virtual full-tank start never sells fuel."""
        if gallons <= _EPSILON or here is None:
            return 0.0
        purchases.append(Purchase(here, gallons))
        return gallons

    while True:
        reach = here_mile + range_miles
        in_range = [i for i in range(next_index, len(stations)) if stations[i].mile <= reach]
        cheaper = next((i for i in in_range if stations[i].price < here_price), None)

        if cheaper is None and trip_miles <= reach:
            buy((trip_miles - here_mile) / mpg - fuel)
            return FuelPlan(purchases)

        if cheaper is not None:
            target = cheaper
            fuel += buy((stations[target].mile - here_mile) / mpg - fuel)
        elif in_range:
            target = min(in_range, key=lambda i: (stations[i].price, -stations[i].mile))
            fuel += buy(capacity - fuel)
        else:
            raise NoFeasiblePlan(
                f"No fuel station within {range_miles:g} miles after mile {here_mile:.0f}."
            )

        here = stations[target]
        fuel -= (here.mile - here_mile) / mpg
        here_mile, here_price, next_index = here.mile, here.price, target + 1
