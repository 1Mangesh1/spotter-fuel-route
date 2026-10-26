from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from planner.geo import sample_indices
from planner.optimizer import BALANCED_STOP_COST, StartTank, Strategy
from planner.places import LocationError, resolve_location

# About two points per mile is enough to draw the route and keeps the response small.
_GEOMETRY_SPACING_MILES = 0.5


class RoundedFloatField(serializers.FloatField):
    def __init__(self, digits: int, **kwargs):
        self.digits = digits
        super().__init__(**kwargs)

    def to_representation(self, value) -> float:
        return round(float(value), self.digits)


class TripQuerySerializer(serializers.Serializer):
    start = serializers.CharField(
        help_text='A US place: "Chicago, IL", "Chicago, Illinois" or "41.88,-87.63".'
    )
    finish = serializers.CharField(
        help_text='A US place: "Denver, CO", "Denver, Colorado" or "39.74,-104.99".'
    )
    start_tank = serializers.ChoiceField(
        choices=[t.value for t in StartTank],
        default=StartTank.EMPTY.value,
        help_text=(
            "empty: pay for every gallon of the trip, starting at the cheapest station within "
            "10 miles of the start. full: start with a full tank and pay only for fuel bought "
            "on the way."
        ),
    )

    strategy = serializers.ChoiceField(
        choices=[s.value for s in Strategy],
        default=Strategy.CHEAPEST.value,
        help_text=(
            "cheapest: the lowest fuel cost, which can mean several small top-ups. "
            f"balanced: counts each stop as ${BALANCED_STOP_COST:g} of driver time, so it makes "
            "far fewer stops for a little more fuel cost. fewest_stops: the minimum number of "
            "stops, and the cheapest plan among those."
        ),
    )

    def _location(self, value: str):
        try:
            return resolve_location(value)
        except LocationError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate_start(self, value):
        return self._location(value)

    def validate_finish(self, value):
        return self._location(value)

    def validate_start_tank(self, value):
        return StartTank(value)

    def validate_strategy(self, value):
        return Strategy(value)


class LocationSerializer(serializers.Serializer):
    label = serializers.CharField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()


class FuelStopSerializer(serializers.Serializer):
    mile_marker = RoundedFloatField(1, source="candidate.mile")
    name = serializers.CharField(source="candidate.station.name")
    address = serializers.CharField(source="candidate.station.address")
    city = serializers.CharField(source="candidate.station.city")
    state = serializers.CharField(source="candidate.station.state")
    price_per_gallon = RoundedFloatField(3, source="candidate.price")
    gallons = RoundedFloatField(2)
    cost = RoundedFloatField(2)
    lat = serializers.FloatField(source="candidate.station.lat")
    lon = serializers.FloatField(source="candidate.station.lon")


class TripPlanSerializer(serializers.Serializer):
    start = LocationSerializer()
    finish = LocationSerializer()
    start_tank = serializers.CharField()
    strategy = serializers.CharField()
    stop_count = serializers.IntegerField(source="fuel.stop_count")
    distance_miles = RoundedFloatField(1, source="route.distance_miles")
    duration_hours = RoundedFloatField(2, source="route.duration_hours")
    fuel_stops = FuelStopSerializer(source="fuel.purchases", many=True)
    total_gallons = RoundedFloatField(2, source="fuel.total_gallons")
    total_fuel_cost = RoundedFloatField(2, source="fuel.total_cost")
    route_geometry = serializers.SerializerMethodField()
    map_url = serializers.SerializerMethodField()

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_route_geometry(self, plan) -> dict:
        """The route as a GeoJSON LineString ([lon, lat] pairs)."""
        route = plan.route
        indices = sample_indices(route.cum_miles, _GEOMETRY_SPACING_MILES)
        coordinates = [
            [round(lon, 5), round(lat, 5)] for lat, lon in (route.points[i] for i in indices)
        ]
        return {"type": "LineString", "coordinates": coordinates}

    def get_map_url(self, plan) -> str:
        """The test page with this trip on a map."""
        request = self.context["request"]
        return request.build_absolute_uri("/?" + request.GET.urlencode())


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
