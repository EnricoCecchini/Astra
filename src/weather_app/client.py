"""HTTP clients and normalized weather data for OpenWeatherMap."""

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any

import requests

from .config import OPEN_WEATHER_BASE_URL, get_api_key


class WeatherError(Exception):
    """A safe, user-facing error while retrieving or interpreting weather."""


@dataclass(frozen=True)
class WeatherReading:
    """Conditions at an observation or forecast time; optional fields may be absent."""

    latitude: float
    longitude: float
    timestamp: datetime
    kind: str
    temperature_c: float | None
    cloud_cover_percent: float | None
    humidity_percent: float | None
    visibility_m: float | None
    wind_speed_mps: float | None
    description: str | None


class BaseAPIClient:
    """Reusable JSON GET client with a timeout and safe error messages."""

    def __init__(self, base_url: str, timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, endpoint: str, params: dict[str, Any]) -> dict:
        try:
            response = requests.get(f"{self.base_url}/{endpoint.lstrip('/')}", params=params, timeout=self.timeout)
        except requests.Timeout:
            raise WeatherError("Weather service timed out. Please try again.") from None
        except requests.RequestException:
            raise WeatherError("Could not connect to the weather service.") from None
        if response.status_code == 401:
            raise WeatherError("OpenWeather rejected the API key. Check that it is correct and active.")
        if response.status_code == 429:
            raise WeatherError("OpenWeather request limit reached. Please try again later.")
        if not response.ok:
            raise WeatherError(f"Weather service returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherError("Weather service returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise WeatherError("Weather service returned an unexpected response.")
        return payload


class OpenWeatherClient(BaseAPIClient):
    """Retrieve current conditions and three-hour forecast slots in metric units."""

    def __init__(self, api_key: str | None = None, timeout: float = 10):
        super().__init__(OPEN_WEATHER_BASE_URL, timeout)
        self._api_key = api_key.strip() if api_key else get_api_key()
        if not self._api_key or self._api_key == "your_key_here":
            raise ValueError("Set OPENWEATHER_API_KEY in variables.env before requesting weather.")

    def _request(self, endpoint: str, latitude: float, longitude: float) -> dict:
        for value, low, high, name in ((latitude, -90, 90, "latitude"), (longitude, -180, 180, "longitude")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be a finite number between {low} and {high}.")
        return self.get_json(endpoint, {"lat": latitude, "lon": longitude, "appid": self._api_key, "units": "metric"})

    def current_weather(self, latitude: float, longitude: float) -> WeatherReading:
        """Return a current observation for the requested coordinates."""
        return self._parse(self._request("weather", latitude, longitude), latitude, longitude, "current")

    def forecast(self, latitude: float, longitude: float) -> list[WeatherReading]:
        """Return the available five-day forecast, typically at three-hour intervals."""
        payload = self._request("forecast", latitude, longitude)
        entries = payload.get("list")
        if not isinstance(entries, list) or not entries:
            raise WeatherError("Weather forecast contains no forecast slots.")
        return [self._parse(entry, latitude, longitude, "forecast") for entry in entries]

    @staticmethod
    def _parse(data: dict, latitude: float, longitude: float, kind: str) -> WeatherReading:
        try:
            if not isinstance(data, dict):
                raise TypeError("Expected an object")
            timestamp = datetime.fromtimestamp(data["dt"], tz=timezone.utc)
            main = data.get("main") or {}
            clouds = data.get("clouds") or {}
            wind = data.get("wind") or {}
            descriptions = data.get("weather") or []
            def number(value, low=None, high=None):
                if value is None:
                    return None
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                    raise ValueError("Invalid weather value")
                if (low is not None and value < low) or (high is not None and value > high):
                    raise ValueError("Weather value outside expected range")
                return float(value)
            return WeatherReading(latitude, longitude, timestamp, kind,
                number(main.get("temp")), number(clouds.get("all"), 0, 100),
                number(main.get("humidity"), 0, 100), number(data.get("visibility"), 0),
                number(wind.get("speed"), 0), descriptions[0].get("description") if descriptions else None)
        except (KeyError, TypeError, ValueError, OverflowError, OSError, AttributeError, IndexError) as exc:
            raise WeatherError("Weather service returned incomplete or invalid data.") from exc


def forecast_for_time(readings: list[WeatherReading], when: datetime) -> WeatherReading | None:
    """Nearest forecast slot within 90 minutes; never extrapolate outside that range."""
    if when.tzinfo is None or when.utcoffset() is None:
        raise ValueError("when must be timezone-aware")
    if not readings:
        return None
    closest = min(readings, key=lambda reading: abs((reading.timestamp - when).total_seconds()))
    return closest if abs((closest.timestamp - when).total_seconds()) <= 90 * 60 else None
