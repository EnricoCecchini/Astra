"""Loading the curated list of observing sites."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Site

SITES_CSV = Path(__file__).resolve().parents[2] / "data" / "sites.csv"


def _optional(value: str, cast):
    return cast(value) if value.strip() else None


def load_sites(path: Path = SITES_CSV) -> list[Site]:
    """Read every row of ``sites.csv`` into a :class:`Site`."""
    with open(path, newline="", encoding="utf-8") as file:
        return [
            Site(
                site_id=row["site_id"],
                name=row["name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                elevation_m=_optional(row["elevation_m"], float) or 0.0,
                owm_location_id=_optional(row["owm_location_id"], int),
                sky_brightness=_optional(row["sky_brightness"], float),
            )
            for row in csv.DictReader(file)
        ]
