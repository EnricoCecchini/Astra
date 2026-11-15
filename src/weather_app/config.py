"""Configuration for the OpenWeather integration."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / "variables.env")
OPEN_WEATHER_BASE_URL = "https://api.openweathermap.org/data/2.5"


def get_api_key() -> str:
    """Read the local key when a client is created, not on module import."""
    key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    if not key or key == "your_key_here":
        raise ValueError("Set OPENWEATHER_API_KEY in variables.env before requesting weather.")
    return key
