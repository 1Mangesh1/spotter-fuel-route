"""Plan one trip: the route, the stations along it, and the fuel stops for a strategy."""

from dataclasses import dataclass

from planner.optimizer import FuelPlan, StartTank, Strategy, plan_with_strategy
from planner.places import Location
from planner.routing import Route, get_route
from planner.stations import Station, get_station_index


@dataclass(frozen=True)
class TripPlan:
    start: Location
    finish: Location
    start_tank: StartTank
    strategy: Strategy
    route: Route
    fuel: FuelPlan[Station]


def plan_trip(
    start: Location, finish: Location, start_tank: StartTank, strategy: Strategy
) -> TripPlan:
    route = get_route(start.point, finish.point)
    candidates = get_station_index().along_route(route.points, route.cum_miles)
    fuel = plan_with_strategy(
        candidates, route.distance_miles, strategy=strategy, start_tank=start_tank
    )
    return TripPlan(start, finish, start_tank, strategy, route, fuel)
