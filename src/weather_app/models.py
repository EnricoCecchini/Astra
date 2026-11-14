"""Data classes shared across modules.

Includes heuristic stargazing suitability scoring (no external dependencies).
Darkness and moonlight suitability are supplied on a 0–100 scale by an
astronomy module; neither can reliably be inferred from weather alone.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from pathlib import Path

from .utils import haversine_km


def _bounded(value: float, low: float, high: float, name: str) -> float:
    if not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return float(value)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


@dataclass(frozen=True)
class ScoreResult:
    timestamp: datetime
    cloud: float
    humidity: float
    visibility: float
    wind: float
    altitude: float
    darkness: float
    moonlight: float
    weather: float
    astronomical: float
    combined: float


class AstroSuitabilityScorer:
    """Score stargazing conditions from measured inputs and astronomy scores.

    All weight tuples must contain nonnegative values summing to 1.
    Visibility reaches 100 at ``ideal_visibility_m``; wind suitability
    reaches 0 at ``unfavorable_wind_mps``. These are tunable heuristics.
    """

    def __init__(
        self,
        weather_weights: tuple[float, float, float, float] = (0.50, 0.20, 0.15, 0.15),
        astronomy_weights: tuple[float, float, float] = (0.50, 0.30, 0.20),
        combined_weights: tuple[float, float] = (0.60, 0.40),
        ideal_visibility_m: float = 10_000,
        unfavorable_wind_mps: float = 10.0,
        output_path: str | Path | None = None,
    ) -> None:
        self.weather_weights = self._validate_weights(weather_weights, 4)
        self.astronomy_weights = self._validate_weights(astronomy_weights, 3)
        self.combined_weights = self._validate_weights(combined_weights, 2)
        self.ideal_visibility_m = self._positive(ideal_visibility_m, "ideal_visibility_m")
        self.unfavorable_wind_mps = self._positive(unfavorable_wind_mps, "unfavorable_wind_mps")
        self.output_path = Path(output_path) if output_path is not None else None

    @staticmethod
    def _positive(value: float, name: str) -> float:
        if not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be a positive finite number")
        return float(value)

    @staticmethod
    def _validate_weights(weights: tuple[float, ...], count: int) -> tuple[float, ...]:
        if len(weights) != count or any(
            not isinstance(w, (int, float)) or not isfinite(w) or w < 0 for w in weights
        ) or abs(sum(weights) - 1) > 1e-9:
            raise ValueError(f"Weights must contain {count} nonnegative values summing to 1")
        return tuple(float(w) for w in weights)

    def score(
        self,
        *,
        timestamp: datetime,
        cloud_cover_percent: float,
        relative_humidity_percent: float,
        visibility_m: float,
        wind_speed_mps: float,
        altitude_degrees: float,
        darkness_suitability: float,
        moonlight_suitability: float,
    ) -> ScoreResult:
        """Compute and append scores for one location, target, and observation time.

        ``moonlight_suitability`` is target-dependent: 100 = ideal moonlight
        for the selected celestial object, 0 = completely unsuitable.
        ``darkness_suitability`` is likewise 100 = fully suitable darkness.
        ``timestamp`` must be timezone-aware to avoid ambiguous time-series data.
        Each successful call appends one row to the configured output CSV.
        File errors propagate to the caller instead of silently losing history.
        """
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        cloud = 100 - _bounded(cloud_cover_percent, 0, 100, "cloud_cover_percent")
        humidity = 100 - _bounded(relative_humidity_percent, 0, 100, "relative_humidity_percent")
        visibility = _clamp(
            self._positive_or_zero(visibility_m, "visibility_m") / self.ideal_visibility_m * 100
        )
        wind = _clamp(
            100 - self._positive_or_zero(wind_speed_mps, "wind_speed_mps")
            / self.unfavorable_wind_mps * 100
        )
        altitude = _bounded(altitude_degrees, -90, 90, "altitude_degrees")
        altitude_score = _clamp(altitude / 60 * 100)
        darkness = _bounded(darkness_suitability, 0, 100, "darkness_suitability")
        moonlight = _bounded(moonlight_suitability, 0, 100, "moonlight_suitability")

        weather = sum(x * w for x, w in zip(
            (cloud, humidity, visibility, wind), self.weather_weights
        ))
        astronomical = sum(x * w for x, w in zip(
            (altitude_score, darkness, moonlight), self.astronomy_weights
        ))
        combined = weather * self.combined_weights[0] + astronomical * self.combined_weights[1]
        result = ScoreResult(
            timestamp, cloud, humidity, visibility, wind, altitude_score, darkness,
            moonlight, weather, astronomical, combined
        )
        self.append_score(result)
        return result

    def append_score(self, result: ScoreResult, path: str | Path | None = None) -> Path:
        """Append a result to the configured CSV, or an explicit custom path.

        Create missing directories and write the header for a new or empty file.
        Existing files must have the same columns as ScoreResult.
        """
        output = Path(path) if path is not None else self.output_path
        if output is None:
            output = Path(__file__).resolve().parents[2] / "data" / "scoring_output.csv"
        row = asdict(result)
        row["timestamp"] = result.timestamp.isoformat()
        columns = list(row)
        output.parent.mkdir(parents=True, exist_ok=True)
        needs_newline = False
        if output.exists() and output.stat().st_size:
            with output.open(newline="", encoding="utf-8") as file:
                if next(csv.reader(file), None) != columns:
                    raise ValueError("Scoring CSV header does not match ScoreResult columns")
            with output.open("rb") as file:
                file.seek(-1, 2)
                needs_newline = file.read(1) not in (b"\n", b"\r")
        with output.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            if file.tell() == 0:
                writer.writeheader()
            elif needs_newline:
                file.write("\n")
            writer.writerow(row)
        return output

    @staticmethod
    def _positive_or_zero(value: float, name: str) -> float:
        if not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a nonnegative finite number")
        return float(value)


@dataclass(frozen=True, kw_only=True)
class Site:
    """One observing site, as listed in ``data/sites.csv``."""

    site_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float = 0.0
    owm_location_id: int | None = None
    sky_brightness: float | None = None  # optional light-pollution value

    def __post_init__(self) -> None:
        if not self.site_id:
            raise ValueError("site_id must not be empty")
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"{self.site_id}: latitude {self.latitude} is outside -90..90")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"{self.site_id}: longitude {self.longitude} is outside -180..180")

    def distance_km(self, lat: float, lon: float) -> float:
        """Straight-line (great-circle) distance from this site to a point."""
        return haversine_km(self.latitude, self.longitude, lat, lon)

    def __repr__(self) -> str:
        return f"Site({self.site_id!r}, {self.latitude:.4f}, {self.longitude:.4f})"
