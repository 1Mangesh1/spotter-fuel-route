"""Build planner/data/us_places.csv from the Census Gazetteer national places file.

Source (public domain):
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip
"""

import csv
import re
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from planner.places import PLACES_CSV, place_key

_SUFFIX = re.compile(
    r"\s+(city and borough|CDP|city|town|village|borough|comunidad|zona urbana|municipality"
    r"|unified government|consolidated government|metropolitan government|metro government"
    r"|urban county|corporation)$"
)
_ALTERNATE = re.compile(r"(.+?) \((.+)\)")
# Consolidated city-county governments, such as "Nashville-Davidson". Their short name
# ("Nashville") is what people type, so it gets an alias.
_CONSOLIDATED_LSAD = {"00", "CG", "MG", "UC", "UG"}


def clean_place_names(raw_name: str, lsad: str) -> list[str]:
    """Names a person would use for one Census place, most official first."""
    name = _SUFFIX.sub("", raw_name.removesuffix(" (balance)"))
    names = list(match.groups()) if (match := _ALTERNATE.fullmatch(name)) else [name]
    if lsad in _CONSOLIDATED_LSAD and re.search(r"[-/]", names[0]):
        names.append(re.split(r"[-/]", names[0])[0])
    return names


class Command(BaseCommand):
    help = "Build the offline US places lookup from the Census Gazetteer places zip."

    def add_arguments(self, parser):
        parser.add_argument("zip_path", type=Path, help="Path to 20XX_Gaz_place_national.zip")

    def handle(self, *args, zip_path: Path, **options):
        if not zip_path.is_file():
            raise CommandError(f"{zip_path} does not exist.")
        with zipfile.ZipFile(zip_path) as archive:
            text = archive.read(archive.namelist()[0]).decode("utf-8")

        rows = csv.DictReader(text.splitlines(), delimiter="|")
        best: dict[tuple[str, str], tuple[float, dict[str, str]]] = {}
        for row in rows:
            land_area = float(row["ALAND"])
            for name in clean_place_names(row["NAME"].strip(), row["LSAD"]):
                key = (place_key(name), row["USPS"])
                # Two places can share a name in one state. Keep the larger one.
                if key not in best or land_area > best[key][0]:
                    lat, lon = row["INTPTLAT"], row["INTPTLONG"].strip()
                    best[key] = (
                        land_area,
                        {"name": name, "state": row["USPS"], "lat": lat, "lon": lon},
                    )

        PLACES_CSV.parent.mkdir(parents=True, exist_ok=True)
        with PLACES_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "state", "lat", "lon"])
            writer.writeheader()
            places = sorted(
                (row for _, row in best.values()), key=lambda r: (r["state"], r["name"])
            )
            writer.writerows(places)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(best)} places to {PLACES_CSV}"))
