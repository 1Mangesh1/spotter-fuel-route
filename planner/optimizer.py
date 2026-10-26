"""Choose where to buy fuel along a route so that the trip costs as little as possible.

The route is one line, so a station is a mile marker and a price. The greedy rule below is
optimal for that case: at each station, buy just enough fuel to reach the next cheaper
station in range. If no station in range is cheaper, fill the tank and drive to the cheapest
station in range.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass
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
    purchases: list[Purchase[T]]

    @property
    def total_gallons(self) -> float:
        return sum(p.gallons for p in self.purchases)

    @property
    def total_cost(self) -> float:
        return sum(p.cost for p in self.purchases)

    @property
    def stop_count(self) -> int:
        return len(self.purchases)


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
        here = _first_stop(stations, start_radius_miles)
        here_mile, here_price, next_index = here.mile, here.price, stations.index(here) + 1
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


def _first_stop[T](stations: list[Candidate[T]], start_radius_miles: float) -> Candidate[T]:
    """With an empty tank, the trip starts at the cheapest station near the start."""
    nearby = [c for c in stations if c.mile <= start_radius_miles]
    if not nearby:
        raise NoFeasiblePlan(
            f"No fuel station within {start_radius_miles:g} miles of the start. "
            "Try start_tank=full."
        )
    return min(nearby, key=lambda c: c.price)


class Strategy(StrEnum):
    CHEAPEST = "cheapest"
    BALANCED = "balanced"
    FEWEST_STOPS = "fewest_stops"


# For the balanced strategy, one stop costs this much (USD). It stands for the driver's time,
# so the plan takes a few cents more fuel cost to save a stop.
BALANCED_STOP_COST = 5.0


def plan_with_strategy[T](
    candidates: Iterable[Candidate[T]],
    trip_miles: float,
    *,
    strategy: Strategy = Strategy.CHEAPEST,
    start_tank: StartTank = StartTank.EMPTY,
    range_miles: float = MAX_RANGE_MILES,
    mpg: float = MILES_PER_GALLON,
    start_radius_miles: float = START_RADIUS_MILES,
) -> FuelPlan[T]:
    """Plan the fuel stops for one strategy.

    CHEAPEST gives the exact lowest fuel cost. BALANCED and FEWEST_STOPS first choose the
    stations to stop at, and then buy at those stations with the same exact rule. That stop
    search is an estimate, so the exact cheapest plan wins when it does at least as well on
    the strategy's own measure.
    """
    options = {
        "start_tank": start_tank,
        "range_miles": range_miles,
        "mpg": mpg,
        "start_radius_miles": start_radius_miles,
    }
    candidates = list(candidates)
    cheapest = plan_fuel(candidates, trip_miles, **options)
    if strategy is Strategy.CHEAPEST:
        return cheapest
    stops = _choose_stops(candidates, trip_miles, strategy=strategy, **options)
    chosen = plan_fuel(stops, trip_miles, **options)
    return min(chosen, cheapest, key=lambda plan: _score(plan, strategy))


def _score(plan: FuelPlan, strategy: Strategy) -> tuple[float, ...]:
    """Lower is better. This is the measure that each strategy minimizes."""
    if strategy is Strategy.FEWEST_STOPS:
        return (plan.stop_count, plan.total_cost)
    if strategy is Strategy.BALANCED:
        return (plan.total_cost + BALANCED_STOP_COST * plan.stop_count,)
    return (plan.total_cost,)


def _choose_stops[T](
    candidates: list[Candidate[T]],
    trip_miles: float,
    *,
    strategy: Strategy,
    start_tank: StartTank,
    range_miles: float,
    mpg: float,
    start_radius_miles: float,
) -> list[Candidate[T]]:
    """Pick the stations to stop at, as a shortest path over the stations in route order.

    The path cost assumes that each stop buys just enough fuel to reach the next stop. That
    estimate ranks the stop sets. plan_fuel then sets the exact amounts for the chosen set.
    """
    stations = sorted((c for c in candidates if 0 <= c.mile <= trip_miles), key=lambda c: c.mile)
    if start_tank is StartTank.FULL and trip_miles <= range_miles:
        return []

    type Value = tuple[int, float]  # (stops, estimated fuel cost)

    def rank(value: Value) -> tuple[float, ...]:
        stops, cost = value
        if strategy is Strategy.FEWEST_STOPS:
            return (stops, cost)
        return (cost + BALANCED_STOP_COST * stops,)

    # A station has two states: reached with an empty tank after the stop before it, or
    # reached straight from a full-tank start with fuel to spare.
    empty: list[Value | None] = [None] * len(stations)
    direct: list[Value | None] = [None] * len(stations)
    previous: list[tuple[int, bool] | None] = [None] * len(stations)
    if start_tank is StartTank.FULL:
        for j, c in enumerate(stations):
            if c.mile <= range_miles:
                direct[j] = (1, 0.0)
    else:
        first = _first_stop(stations, start_radius_miles)
        f = stations.index(first)
        empty[f] = (1, first.price * first.mile / mpg)

    finish: tuple[Value, int, bool] | None = None
    for i, here in enumerate(stations):
        for from_start, value in ((False, empty[i]), (True, direct[i])):
            if value is None:
                continue
            stops, cost = value
            spare = range_miles - here.mile if from_start else 0.0
            # A stop must buy fuel. If the spare fuel covers the next leg, the plan that
            # skips this station is already in the search.
            left = trip_miles - here.mile
            if left <= range_miles and (left > spare or not from_start):
                done = (stops, cost + here.price * (left - spare) / mpg)
                if finish is None or rank(done) < rank(finish[0]):
                    finish = (done, i, from_start)
            for j in range(i + 1, len(stations)):
                gap = stations[j].mile - here.mile
                if gap > range_miles:
                    break
                if gap <= spare:
                    continue
                candidate = (stops + 1, cost + here.price * (gap - spare) / mpg)
                if empty[j] is None or rank(candidate) < rank(empty[j]):
                    empty[j], previous[j] = candidate, (i, from_start)

    if finish is None:
        raise NoFeasiblePlan(
            f"No set of stations covers the trip with a {range_miles:g}-mile range."
        )
    _, i, from_start = finish
    path = [stations[i]]
    while not from_start and previous[i] is not None:
        i, from_start = previous[i]
        path.append(stations[i])
    return path[::-1]
