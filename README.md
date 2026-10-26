# Fuel Route Planner

A Django API that plans a truck trip between two places in the USA. It returns the route, the fuel stops to make, and the total fuel cost. The truck has a 500-mile range and uses 1 gallon every 10 miles. Fuel prices come from the Spotter price list in `planner/data/fuel_prices.csv`.

A new start and finish pair makes one call to the routing API. A repeated pair makes none, because the server caches the route.

## Run it

You need [uv](https://docs.astral.sh/uv/). It installs Python 3.13 and the packages.

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py import_stations planner/data/fuel_prices.csv
uv run python manage.py runserver
```

Then open these pages:

| Page | What it is |
|---|---|
| http://127.0.0.1:8000/ | Test page: a form, the route on a map, the fuel stops, a plan comparison and the raw JSON |
| http://127.0.0.1:8000/api/docs/ | Swagger UI |
| http://127.0.0.1:8000/api/redoc/ | ReDoc |
| http://127.0.0.1:8000/api/schema/ | OpenAPI 3 schema |

`postman_collection.json` has four ready requests.

## The API

`GET /api/route/`

| Parameter | Values | Default |
|---|---|---|
| `start` | A US place: `Chicago, IL`, `Chicago, Illinois` or `41.88,-87.63` | required |
| `finish` | The same forms as `start` | required |
| `start_tank` | `empty` or `full` | `empty` |
| `strategy` | `cheapest`, `balanced` or `fewest_stops` | `cheapest` |

`start_tank` decides what the total cost counts:

- `empty`: the truck pays for every gallon of the trip. It first fills at the cheapest station within 10 miles of the start.
- `full`: the truck starts with 50 gallons, and only fuel bought on the way counts.

`strategy` decides what "optimal" means:

- `cheapest`: the lowest fuel cost. This plan is exact. On a long trip, it can make small top-ups where prices rise ahead.
- `balanced`: each stop also counts as $5 of driver time. The plan makes far fewer stops for a little more fuel cost.
- `fewest_stops`: the smallest number of stops, and the cheapest plan with that many stops.

Example: `GET /api/route/?start=Chicago, IL&finish=Denver, CO&strategy=balanced` (shortened):

```json
{
  "start": {"label": "Chicago, IL", "lat": 41.837045, "lon": -87.684939},
  "finish": {"label": "Denver, CO", "lat": 39.76185, "lon": -104.881105},
  "start_tank": "empty",
  "strategy": "balanced",
  "stop_count": 4,
  "distance_miles": 1000.7,
  "duration_hours": 17.79,
  "fuel_stops": [
    {"mile_marker": 0.0, "name": "Gas N Wash", "address": "I-55, EXIT 285", "city": "Chicago", "state": "IL",
     "price_per_gallon": 3.399, "gallons": 1.47, "cost": 4.99, "lat": 41.837045, "lon": -87.684939},
    {"mile_marker": 14.7, "name": "Gulf", "address": "SR-83", "city": "Bensenville", "state": "IL",
     "price_per_gallon": 3.059, "gallons": 18.76, "cost": 57.37, "lat": 41.958011, "lon": -87.943825}
  ],
  "total_gallons": 100.07,
  "total_fuel_cost": 292.37,
  "route_geometry": {"type": "LineString", "coordinates": [[-87.68488, 41.83705], [-87.68526, 41.84034]]},
  "map_url": "http://127.0.0.1:8000/?start=Chicago%2C+IL&finish=Denver%2C+CO&strategy=balanced"
}
```

`route_geometry` is GeoJSON, so any map library can draw it. `map_url` opens the same trip on the test page.

| Status | When |
|---|---|
| 200 | The plan is ready. |
| 400 | A parameter is missing, a place is not in the USA, or a value is not allowed. The body names the field. |
| 422 | No road connects the places, or the stations cannot cover the trip with a 500-mile range. |
| 502 | The routing service failed or did not answer. |

## How it works

1. **Places, with no API call.** `planner/places.py` reads `planner/data/us_places.csv`, which holds about 46,000 US places from the Census Gazetteer files. The lookup takes "City, ST" or "City, State", and it uses a lat,lon pair as given.
2. **One routing call.** `planner/routing.py` asks the public [OSRM](https://project-osrm.org/) server for the route as GeoJSON. The server caches each route for 24 hours.
3. **Stations near the route.** The price list has no coordinates. `import_stations` places each station at the Census point of its city and stores it in SQLite. At request time, `planner/stations.py` keeps the stations within 10 miles of the route. A grid of 0.5-degree cells means that each route point checks only the stations near it.
4. **The fuel plan.** `planner/optimizer.py` holds all three strategies.
   - `cheapest` is a greedy rule that is exact for a single route. At each station, the truck buys just enough fuel to reach the next cheaper station in range. If no station in range is cheaper, it fills the tank and drives to the cheapest station in range.
   - `balanced` and `fewest_stops` first choose the stations to stop at, with a shortest-path search over the stations in route order. The greedy rule then sets the amount to buy at each chosen station.

## Speed

These numbers come from a laptop with the full price list loaded:

| Request | Time |
|---|---|
| New start and finish (one OSRM call) | 0.8 to 1.9 s |
| Same trip again, or another strategy for it | 10 to 110 ms |

Results for New York, NY to Los Angeles, CA (2,806 miles) with an empty tank:

| Strategy | Stops | Fuel cost |
|---|---|---|
| `cheapest` | 17 | $851.10 |
| `balanced` | 7 | $858.77 |
| `fewest_stops` | 6 | $907.61 |

## Assumptions and limits

- A station's position is the center of its city. The plan does not add the short detour from the highway to the station.
- The price list repeats some stations with different prices, one row per supply rack. The import keeps the lowest price for each station.
- The import places 6,431 of the 6,738 stations. It skips 112 stations in Canada and 195 in small US communities that no Census file lists. The import prints their names.
- `balanced` and `fewest_stops` choose their stops with an estimate that assumes each stop buys just enough to reach the next one. The amounts at the chosen stops are then exact. Only `cheapest` is exact end to end.
- The public OSRM server is a demo service. For production, set `OSRM_BASE_URL` to your own OSRM server.

## Tests

```bash
uv run python manage.py test planner
uv run ruff check . && uv run ruff format --check .
```

The tests use hand-computed numbers. The tests replace only the HTTP call to OSRM, with a fixed route.

## Rebuild the places file

The `build_places` command makes `planner/data/us_places.csv` from two public-domain Census files:

```bash
uv run python manage.py build_places 2025_Gaz_place_national.zip --cousubs 2025_Gaz_cousubs_national.zip
```

Download them from https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/.
