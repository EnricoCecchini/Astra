"""Read the most recent collected readings back from the weather CSV logs.

The collector (``scripts/collect_weather.py``) is the only part of the project
that requests weather from the API. The app reads what it saved, so pressing
buttons never adds rows to the history.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .client import WeatherReading
from .storage import DATA_DIR

FILES = {"current": "historical_weather.csv", "forecast": "forecast_weather.csv"}
NUMERIC_FIELDS = ("temperature_c", "cloud_cover_percent", "humidity_percent",
                  "visibility_m", "wind_speed_mps")


def location_key(latitude: float, longitude: float) -> tuple[float, float]:
    """Coordinates rounded so a site's logged rows match the site itself."""
    return round(float(latitude), 6), round(float(longitude), 6)


@dataclass(frozen=True)
class SavedFetch:
    """All readings one collector request saved for one location."""

    fetched_at: datetime
    readings: tuple[WeatherReading, ...]

    @property
    def latest_reading(self) -> WeatherReading:
        """The reading with the latest observation or forecast time."""
        return max(self.readings, key=lambda reading: reading.timestamp)


def _optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


def _parse_row(row: dict[str, str]) -> tuple[datetime, WeatherReading]:
    fetched_at = datetime.fromisoformat(row["fetched_at"])
    timestamp = datetime.fromisoformat(row["timestamp"])
    if fetched_at.tzinfo is None or timestamp.tzinfo is None:
        raise ValueError("Logged times must be timezone-aware")
    reading = WeatherReading(
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        timestamp=timestamp,
        kind=row["kind"],
        description=row.get("description") or None,
        **{name: _optional_float(row.get(name)) for name in NUMERIC_FIELDS},
    )
    return fetched_at, reading


def latest_fetches(kind: str, data_dir: str | Path = DATA_DIR) -> dict[tuple[float, float], SavedFetch]:
    """The most recent saved fetch of ``kind`` ("current" or "forecast") per location.

    Malformed rows are skipped. A missing log file means nothing was collected yet.
    """
    if kind not in FILES:
        raise ValueError(f"kind must be one of {sorted(FILES)}")
    path = Path(data_dir) / FILES[kind]
    if not path.exists():
        return {}
    batches: dict[tuple[float, float], tuple[datetime, list[WeatherReading]]] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row.get("kind") != kind:
                continue
            try:
                fetched_at, reading = _parse_row(row)
            except (KeyError, TypeError, ValueError):
                continue
            key = location_key(reading.latitude, reading.longitude)
            newest = batches.get(key)
            if newest is None or fetched_at > newest[0]:
                batches[key] = (fetched_at, [reading])
            elif fetched_at == newest[0]:
                newest[1].append(reading)
    return {key: SavedFetch(fetched_at, tuple(readings))
            for key, (fetched_at, readings) in batches.items()}
