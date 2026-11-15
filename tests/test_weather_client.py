"""Focused offline tests for the OpenWeather client."""
import unittest
import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests

from weather_app.client import OpenWeatherClient, WeatherError, forecast_for_time


class WeatherClientTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data_dir = Path(self.temporary.name) / "data"
        self.client = OpenWeatherClient(api_key="test-key", data_dir=self.data_dir)
        self.raw = {"dt": 1700000000, "main": {"temp": 12.5, "humidity": 60},
                    "clouds": {"all": 25}, "visibility": 10000,
                    "wind": {"speed": 2}, "weather": [{"description": "clear sky"}]}

    def response(self, payload, status=200):
        return Mock(status_code=status, ok=status < 400, json=Mock(return_value=payload))

    @patch("weather_app.client.requests.get")
    def test_api_results_append_to_separate_history_files(self, get):
        for _ in range(2):
            get.return_value = self.response(self.raw)
            self.client.current_weather(40, -3)
            get.return_value = self.response({"list": [self.raw, {"dt": 1700010800}]})
            self.client.forecast(40, -3)
        for filename, count, kind in (("historical_weather.csv", 2, "current"),
                                      ("forecast_weather.csv", 4, "forecast")):
            with (self.data_dir / filename).open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), count)
            self.assertTrue(all(row["kind"] == kind for row in rows))
            self.assertTrue(all(datetime.fromisoformat(row["fetched_at"]).tzinfo for row in rows))
            self.assertEqual(float(rows[0]["humidity_percent"]), 60)
            self.assertEqual(float(rows[0]["latitude"]), 40)
        self.assertEqual(rows[1]["visibility_m"], "")

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
    def test_invalid_later_slot_does_not_discard_viewing_forecast(self, get):
        invalid = {**self.raw, "dt": self.raw["dt"] + 3 * 3600,
                   "main": {"temp": 4.25, "humidity": 101}}
        get.return_value = self.response({"list": [invalid, self.raw, None]})
        readings = self.client.forecast(40, -3)
        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].humidity_percent, 60)
        self.assertIs(forecast_for_time(readings, readings[0].timestamp), readings[0])
        self.assertIsNone(forecast_for_time(
            readings, readings[0].timestamp + timedelta(hours=3)))

    @patch("weather_app.client.requests.get")
    def test_all_invalid_forecast_slots_report_an_error(self, get):
        get.return_value = self.response({"list": [None, {**self.raw, "main": {"humidity": 101}}]})
        with self.assertRaisesRegex(WeatherError, "no valid forecast slots"):
            self.client.forecast(40, -3)

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
