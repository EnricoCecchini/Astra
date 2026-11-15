"""Focused offline tests for the OpenWeather client."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests

from weather_app.client import OpenWeatherClient, WeatherError, forecast_for_time


class WeatherClientTests(unittest.TestCase):
    def setUp(self):
        self.client = OpenWeatherClient(api_key="test-key")
        self.raw = {"dt": 1700000000, "main": {"temp": 12.5, "humidity": 60},
                    "clouds": {"all": 25}, "visibility": 10000,
                    "wind": {"speed": 2}, "weather": [{"description": "clear sky"}]}

    def response(self, payload, status=200):
        return Mock(status_code=status, ok=status < 400, json=Mock(return_value=payload))

    @patch("weather_app.client.requests.get")
    def test_current_request_and_units(self, get):
        get.return_value = self.response(self.raw)
        result = self.client.current_weather(40.4, -3.7)
        self.assertEqual((result.kind, result.cloud_cover_percent, result.temperature_c), ("current", 25, 12.5))
        self.assertEqual(result.timestamp.tzinfo, timezone.utc)
        self.assertEqual(get.call_args.kwargs["params"]["units"], "metric")
        self.assertEqual(get.call_args.kwargs["timeout"], 10)

    @patch("weather_app.client.requests.get")
    def test_forecast_and_optional_missing_fields(self, get):
        get.return_value = self.response({"list": [{"dt": 1700000000}, self.raw]})
        result = self.client.forecast(40, -3)
        self.assertEqual(len(result), 2)
        self.assertIsNone(result[0].visibility_m)
        self.assertEqual(result[1].kind, "forecast")

    @patch("weather_app.client.requests.get")
    def test_http_error_and_timeout_do_not_expose_key(self, get):
        for code in (401, 429, 500):
            get.return_value = self.response({}, code)
            with self.assertRaises(WeatherError) as caught:
                self.client.current_weather(40, -3)
            self.assertNotIn("test-key", str(caught.exception))
        get.side_effect = requests.Timeout("test-key")
        with self.assertRaises(WeatherError) as caught:
            self.client.forecast(40, -3)
        self.assertNotIn("test-key", str(caught.exception))

    @patch("weather_app.client.requests.get")
    def test_bad_data_and_invalid_coordinates(self, get):
        get.return_value = self.response({"list": [{"dt": 1700000000, "clouds": {"all": 101}}]})
        with self.assertRaises(WeatherError):
            self.client.forecast(40, -3)
        with self.assertRaises(ValueError):
            self.client.current_weather(91, 0)
        get.return_value.json.side_effect = ValueError("bad json")
        with self.assertRaises(WeatherError):
            self.client.current_weather(40, -3)

    def test_matching_forecast_respects_time_limit(self):
        reading = self.client._parse(self.raw, 40, -3, "forecast")
        self.assertIs(forecast_for_time([reading], reading.timestamp + timedelta(minutes=90)), reading)
        self.assertIsNone(forecast_for_time([reading], reading.timestamp + timedelta(minutes=91)))
        with self.assertRaises(ValueError):
            forecast_for_time([reading], datetime(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
