"""HTTP clients and normalized weather data for OpenWeatherMap."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any

import requests

from .config import OPEN_WEATHER_BASE_URL, get_api_key
from .storage import DATA_DIR, append_weather

# Letters first, then letters, digits, spaces and common place-name punctuation
# (e.g. "Madrid", "San Sebastián", "Saint-Étienne", "Madrid,ES").
CITY_PATTERN = re.compile(r"[^\W\d_][\w\s,.'-]*")
MAX_CITY_LENGTH = 100


class APIError(Exception):
    """A safe, user-facing error raised by any JSON API client."""


class WeatherError(APIError):
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

    @property
    def scoring_inputs(self) -> dict[str, float | None]:
        """The weather fields the suitability scorer needs, keyed by its argument names."""
        return {
            "cloud_cover_percent": self.cloud_cover_percent,
            "relative_humidity_percent": self.humidity_percent,
            "visibility_m": self.visibility_m,
            "wind_speed_mps": self.wind_speed_mps,
        }

    @property
    def missing_scoring_fields(self) -> list[str]:
        """Names of the scoring inputs this reading lacks (empty when it can be scored)."""
        return [name for name, value in self.scoring_inputs.items() if value is None]


class BaseAPIClient:
    """Reusable JSON GET client with a timeout and safe error messages.

    Nothing here is specific to weather or to OpenWeather: a subclass names the
    service and chooses the exception type its callers catch.
    """

    service_name = "The data service"
    error_type: type[APIError] = APIError

    def __init__(self, base_url: str, timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, endpoint: str, params: dict[str, Any],
                 not_found_message: str | None = None) -> dict:
        """GET ``endpoint`` and return its JSON object, raising ``error_type`` on any failure."""
        name, error = self.service_name, self.error_type
        try:
            response = requests.get(f"{self.base_url}/{endpoint.lstrip('/')}", params=params, timeout=self.timeout)
        except requests.Timeout:
            raise error(f"{name} timed out. Please try again.") from None
        except requests.RequestException:
            raise error(f"Could not connect to {name}. Check your internet connection.") from None
        if response.status_code == 401:
            raise error(f"{name} rejected the API key. Check that it is correct and active.")
        if response.status_code == 404:
            raise error(not_found_message or f"{name} could not find the requested location.")
        if response.status_code == 429:
            raise error(f"{name} request limit reached. Please try again later.")
        if response.status_code >= 500:
            raise error(f"{name} is having problems (HTTP {response.status_code}). Please try again later.")
        if not response.ok:
            raise error(f"{name} returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as exc:
            raise error(f"{name} returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise error(f"{name} returned an unexpected response.")
        return payload


class OpenWeatherClient(BaseAPIClient):
    """Retrieve current conditions and three-hour forecast slots in metric units."""

    service_name = "OpenWeather"
    error_type = WeatherError

    def __init__(self, api_key: str | None = None, timeout: float = 10,
                 data_dir: str | Path = DATA_DIR):
        super().__init__(OPEN_WEATHER_BASE_URL, timeout)
        # Name-mangled so neither callers nor subclasses can read or log the secret by accident.
        self.__api_key = api_key.strip() if api_key else get_api_key()
        self.data_dir = Path(data_dir)
        if not self.__api_key or self.__api_key == "your_key_here":
            raise ValueError("Set OPENWEATHER_API_KEY in variables.env before requesting weather.")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r}, data_dir={str(self.data_dir)!r})"

    def _request(self, endpoint: str, latitude: float, longitude: float) -> dict:
        for value, low, high, name in ((latitude, -90, 90, "latitude"), (longitude, -180, 180, "longitude")):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be a finite number between {low} and {high}.")
        return self.get_json(endpoint, self._params(lat=latitude, lon=longitude))

    def _params(self, **query: Any) -> dict[str, Any]:
        return {**query, "appid": self.__api_key, "units": "metric"}

    @staticmethod
    def validate_city(city: str) -> str:
        """Return the cleaned city name, or raise ``ValueError`` before any request is made."""
        if not isinstance(city, str) or not city.strip():
            raise ValueError("Enter a city name.")
        city = " ".join(city.split())
        if len(city) > MAX_CITY_LENGTH:
            raise ValueError(f"City names are at most {MAX_CITY_LENGTH} characters.")
        if not CITY_PATTERN.fullmatch(city):
            raise ValueError("A city name must start with a letter and contain only letters, "
                             "spaces, commas, periods, apostrophes or hyphens.")
        return city

    def current_weather(self, latitude: float, longitude: float) -> WeatherReading:
        """Fetch a current observation and append it to historical_weather.csv."""
        reading = self._parse(self._request("weather", latitude, longitude), latitude, longitude, "current")
        self._save_readings([reading], "historical_weather.csv")
        return reading

    def current_weather_for_city(self, city: str) -> WeatherReading:
        """Fetch current conditions by city name; the reading carries the city's coordinates."""
        city = self.validate_city(city)
        payload = self.get_json("weather", self._params(q=city),
                                not_found_message=f"No city called {city!r} was found. Check the spelling.")
        coord = payload.get("coord")
        if not isinstance(coord, dict):
            raise WeatherError("OpenWeather returned incomplete or invalid data.")
        latitude, longitude = coord.get("lat"), coord.get("lon")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and isfinite(v)
                   for v in (latitude, longitude)):
            raise WeatherError("OpenWeather returned incomplete or invalid data.")
        reading = self._parse(payload, float(latitude), float(longitude), "current")
        self._save_readings([reading], "historical_weather.csv")
        return reading

    def forecast(self, latitude: float, longitude: float) -> list[WeatherReading]:
        """Return the available five-day forecast, typically at three-hour intervals."""
        payload = self._request("forecast", latitude, longitude)
        entries = payload.get("list")
        if not isinstance(entries, list) or not entries:
            raise WeatherError("Weather forecast contains no forecast slots.")
        # One malformed future slot must not discard otherwise usable forecasts.
        readings = []
        for entry in entries:
            try:
                readings.append(self._parse(entry, latitude, longitude, "forecast"))
            except WeatherError:
                continue
        if not readings:
            raise WeatherError("Weather forecast contains no valid forecast slots.")
        self._save_readings(readings, "forecast_weather.csv")
        return readings

    def _save_readings(self, readings: list[WeatherReading], filename: str) -> None:
        try:
            append_weather(readings, self.data_dir / filename)
        except (OSError, ValueError) as exc:
            raise WeatherError(f"Could not save weather history to {filename}.") from exc

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
