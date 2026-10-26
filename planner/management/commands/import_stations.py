"""Load the Spotter fuel price CSV into the FuelStation table."""

import csv
from collections import Counter
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from planner.models import FuelStation
from planner.places import lookup_city


class Command(BaseCommand):
    help = "Replace all fuel stations with the rows of the Spotter price CSV."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path)

    def handle(self, *args, csv_path: Path, **options):
        if not csv_path.is_file():
            raise CommandError(f"{csv_path} does not exist.")
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        # A station can appear once per supply rack. A driver pays the lowest price.
        cheapest: dict[int, dict[str, str]] = {}
        for row in rows:
            opis_id = int(row["OPIS Truckstop ID"])
            best = cheapest.get(opis_id)
            if best is None or Decimal(row["Retail Price"]) < Decimal(best["Retail Price"]):
                cheapest[opis_id] = row

        stations, unmatched = [], Counter()
        for opis_id, row in cheapest.items():
            city, state = row["City"].strip(), row["State"].strip()
            location = lookup_city(city, state)
            if location is None:
                unmatched[f"{city}, {state}"] += 1
                continue
            stations.append(
                FuelStation(
                    opis_id=opis_id,
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=city,
                    state=state,
                    price=Decimal(row["Retail Price"]).quantize(Decimal("0.001")),
                    lat=location.lat,
                    lon=location.lon,
                )
            )

        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(stations)

        self.stdout.write(
            self.style.SUCCESS(f"Imported {len(stations)} stations from {len(rows)} rows.")
        )
        if unmatched:
            places = ", ".join(place for place, _ in unmatched.most_common(15))
            self.stdout.write(
                f"Skipped {sum(unmatched.values())} stations whose city is not in the Census "
                f"places file: {places}"
            )
