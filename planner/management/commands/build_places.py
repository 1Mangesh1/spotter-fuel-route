"""Build planner/data/us_places.csv from the Census Gazetteer files (public domain).

Places (cities, towns, CDPs):
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_place_national.zip
County subdivisions (townships and New England towns), optional:
https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_cousubs_national.zip
"""

import csv
import re
import zipfile
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from planner.places import PLACES_CSV, place_key

_SUFFIX = re.compile(
    r"\s+(city and borough|charter township|township|CDP|CCD|city|town|village|borough"
    r"|comunidad|zona urbana|barrio|municipality|plantation|UT|gore|grant|purchase|location"
    r"|district|precinct|unified government|consolidated government|metropolitan government"
    r"|metro government|urban county|corporation)$"
)
_ALTERNATE = re.compile(r"(.+?) \((.+)\)")
# Consolidated city-county governments, such as "Nashville-Davidson". Their short name
# ("Nashville") is what people type, so it gets an alias.
_CONSOLIDATED_LSAD = {"00", "CG", "MG", "UC", "UG"}

type Record = dict[str, str]


def clean_place_names(raw_name: str, lsad: str) -> list[str]:
    """Names a person would use for one Census area, most official first."""
    name = _SUFFIX.sub("", raw_name.removesuffix(" (balance)"))
    names = list(match.groups()) if (match := _ALTERNATE.fullmatch(name)) else [name]
    if lsad in _CONSOLIDATED_LSAD and re.search(r"[-/]", names[0]):
        names.append(re.split(r"[-/]", names[0])[0])
    return names


def _read_gazetteer(zip_path: Path) -> list[dict[str, str]]:
    if not zip_path.is_file():
        raise CommandError(f"{zip_path} does not exist.")
    with zipfile.ZipFile(zip_path) as archive:
        text = archive.read(archive.namelist()[0]).decode("utf-8")
    return list(csv.DictReader(text.splitlines(), delimiter="|"))


def _entries(rows: list[dict[str, str]]):
    """Yield (lookup key, land area, output record) for every usable name in the rows."""
    for row in rows:
        lat, lon = row["INTPTLAT"], row["INTPTLONG"].strip()
        for name in clean_place_names(row["NAME"].strip(), row.get("LSAD", "")):
            record = {"name": name, "state": row["USPS"], "lat": lat, "lon": lon}
            yield (place_key(name), row["USPS"]), float(row["ALAND"]), record


class Command(BaseCommand):
    help = "Build the offline US places lookup from the Census Gazetteer files."

    def add_arguments(self, parser):
        parser.add_argument("places_zip", type=Path, help="20XX_Gaz_place_national.zip")
        parser.add_argument("--cousubs", type=Path, help="20XX_Gaz_cousubs_national.zip")

    def handle(self, *args, places_zip: Path, cousubs: Path | None, **options):
        best: dict[tuple[str, str], tuple[float, Record]] = {}
        for key, land_area, record in _entries(_read_gazetteer(places_zip)):
            # Two places can share a name in one state. Keep the larger one.
            if key not in best or land_area > best[key][0]:
                best[key] = (land_area, record)

        if cousubs:
            # Many states repeat township names ("Washington township"). A repeated name
            # cannot tell us which one a station is in, so only unique names are added.
            entries = list(_entries(_read_gazetteer(cousubs)))
            seen = Counter(key for key, _, _ in entries)
            for key, land_area, record in entries:
                if seen[key] == 1 and key not in best:
                    best[key] = (land_area, record)

        PLACES_CSV.parent.mkdir(parents=True, exist_ok=True)
        with PLACES_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "state", "lat", "lon"])
            writer.writeheader()
            records = (record for _, record in best.values())
            writer.writerows(sorted(records, key=lambda r: (r["state"], r["name"])))
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(best)} places to {PLACES_CSV}"))
