# Your data classes go here (e.g. a snapshot of one location's conditions at one point in time).
# README "1. Object-oriented design": special methods (__str__/__repr__/__eq__/__lt__...) and an @property.
"""Heuristic stargazing suitability scoring (no external dependencies).

Darkness and moonlight suitability are supplied on a 0–100 scale by an
astronomy module; neither can reliably be inferred from weather alone.
"""

from dataclasses import dataclass
from datetime import datetime
from math import isfinite


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
    ) -> None:
        self.weather_weights = self._validate_weights(weather_weights, 4)
        self.astronomy_weights = self._validate_weights(astronomy_weights, 3)
        self.combined_weights = self._validate_weights(combined_weights, 2)
        self.ideal_visibility_m = self._positive(ideal_visibility_m, "ideal_visibility_m")
        self.unfavorable_wind_mps = self._positive(unfavorable_wind_mps, "unfavorable_wind_mps")

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
        """Compute scores for one location, target, and observation time.

        ``moonlight_suitability`` is target-dependent: 100 = ideal moonlight
        for the selected celestial object, 0 = completely unsuitable.
        ``darkness_suitability`` is likewise 100 = fully suitable darkness.
        ``timestamp`` must be timezone-aware to avoid ambiguous time-series data.
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
        return ScoreResult(
            timestamp, cloud, humidity, visibility, wind, altitude_score, darkness,
            moonlight, weather, astronomical, combined
        )

    @staticmethod
    def _positive_or_zero(value: float, name: str) -> float:
        if not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
            raise ValueError(f"{name} must be a nonnegative finite number")
        return float(value)
