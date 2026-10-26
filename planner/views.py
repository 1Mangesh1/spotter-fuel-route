from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.optimizer import NoFeasiblePlan
from planner.routing import NoRouteFound, RoutingError
from planner.serializers import ErrorSerializer, TripPlanSerializer, TripQuerySerializer
from planner.services import plan_trip


class RoutePlanView(APIView):
    @extend_schema(
        summary="Plan a route with fuel stops",
        parameters=[TripQuerySerializer],
        responses={
            200: TripPlanSerializer,
            400: OpenApiResponse(description="A field is missing, or a place is not in the USA."),
            422: OpenApiResponse(
                ErrorSerializer, description="No road route, or no fuel plan can finish the trip."
            ),
            502: OpenApiResponse(ErrorSerializer, description="The routing service failed."),
        },
    )
    def get(self, request: Request) -> Response:
        query = TripQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        try:
            plan = plan_trip(**query.validated_data)
        except (NoRouteFound, NoFeasiblePlan) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        except RoutingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
        return Response(TripPlanSerializer(plan, context={"request": request}).data)
