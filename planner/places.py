"""Offline lookup of US locations from the Census places file. No API call is made."""

import csv
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from planner.geo import LatLon

PLACES_CSV = Path(__file__).parent / "data" / "us_places.csv"

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "puerto rico": "PR", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY",
}  # fmt: skip
_CODES = frozenset(STATE_CODES.values())

# A rough box around the 50 states and Puerto Rico. It rejects points on other continents.
_US_LAT = (17.5, 71.5)
_US_LON = (-179.9, -64.5)

_SHORT_WORDS = {"saint": "st", "fort": "ft", "mount": "mt"}
_COORDS = re.compile(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*")


class LocationError(ValueError):
    """The text does not name a location in the USA that we can find."""


@dataclass(frozen=True)
class Location:
    label: str
    lat: float
    lon: float

    @property
    def point(self) -> LatLon:
        return (self.lat, self.lon)


def place_key(name: str) -> str:
    """Normalize a place name so that "St. Louis" and "SAINT LOUIS" match."""
    text = re.sub(r"[-/]", " ", name.lower())
    words = re.sub(r"[^a-z0-9 ]", "", text).split()
    return " ".join(_SHORT_WORDS.get(word, word) for word in words)


def state_code(text: str) -> str | None:
    text = text.strip()
    if text.upper() in _CODES:
        return text.upper()
    return STATE_CODES.get(text.lower())


@cache
def _places() -> dict[tuple[str, str], tuple[str, float, float]]:
    with PLACES_CSV.open(newline="", encoding="utf-8") as f:
        return {
            (place_key(row["name"]), row["state"]): (
                row["name"],
                float(row["lat"]),
                float(row["lon"]),
            )
            for row in csv.DictReader(f)
        }


def lookup_city(city: str, state: str) -> Location | None:
    """Find a place by city name and two-letter state code."""
    found = _places().get((place_key(city), state))
    if found is None:
        return None
    name, lat, lon = found
    return Location(f"{name}, {state}", lat, lon)


def in_usa(lat: float, lon: float) -> bool:
    return _US_LAT[0] <= lat <= _US_LAT[1] and _US_LON[0] <= lon <= _US_LON[1]


def resolve_location(text: str) -> Location:
    """Turn "City, ST", "City, State" or "lat,lon" into a Location."""
    if match := _COORDS.fullmatch(text):
        lat, lon = float(match[1]), float(match[2])
        if not in_usa(lat, lon):
            raise LocationError(f"{text.strip()} is outside the USA.")
        return Location(f"{lat}, {lon}", lat, lon)

    city, comma, state = text.rpartition(",")
    if not comma or not city.strip():
        raise LocationError(f'Use "City, ST" or "lat,lon", like "Chicago, IL". Got "{text}".')
    code = state_code(state)
    if code is None:
        raise LocationError(f'"{state.strip()}" is not a US state.')
    location = lookup_city(city, code)
    if location is None:
        raise LocationError(f"No US place called {city.strip()}, {code}.")
    return location
