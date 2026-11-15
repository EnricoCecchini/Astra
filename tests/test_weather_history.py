"""Reading the latest collected readings back from the CSV logs."""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from weather_app.client import WeatherReading
from weather_app.history import latest_fetches, location_key
from weather_app.storage import append_weather

T0 = datetime(2026, 11, 15, 18, tzinfo=timezone.utc)


def reading(kind, timestamp, latitude=40.4169, longitude=-3.7035, clouds=10.0):
    return WeatherReading(latitude, longitude, timestamp, kind, 12.0, clouds, 40.0,
                          None, 2.0, "clear sky")


class WeatherHistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data_dir = Path(temporary.name)

    def save(self, readings, filename, fetched_at):
        with patch("weather_app.storage.datetime") as clock:
            clock.now.return_value = fetched_at
            append_weather(readings, self.data_dir / filename)

    def test_missing_log_means_nothing_collected(self):
        self.assertEqual(latest_fetches("forecast", self.data_dir), {})
        with self.assertRaises(ValueError):
            latest_fetches("hourly", self.data_dir)

    def test_only_newest_forecast_batch_per_location_is_returned(self):
        old = [reading("forecast", T0 + timedelta(hours=h), clouds=90) for h in (0, 3)]
        new = [reading("forecast", T0 + timedelta(hours=h)) for h in (3, 6, 9)]
        other = [reading("forecast", T0, latitude=40.7856, longitude=-4.0042)]
        self.save(old, "forecast_weather.csv", T0 - timedelta(hours=1))
        self.save(new, "forecast_weather.csv", T0)
        self.save(other, "forecast_weather.csv", T0 - timedelta(hours=2))
        fetches = latest_fetches("forecast", self.data_dir)
        madrid = fetches[location_key(40.4169, -3.7035)]
        self.assertEqual(madrid.fetched_at, T0)
        self.assertEqual(madrid.readings, tuple(new))
        self.assertEqual(madrid.latest_reading.timestamp, T0 + timedelta(hours=9))
        self.assertIsNone(madrid.readings[0].visibility_m)  # blank cells stay missing
        self.assertEqual(len(fetches[location_key(40.7856, -4.0042)].readings), 1)

    def test_latest_current_reading_and_malformed_rows(self):
        self.save([reading("current", T0 - timedelta(minutes=5))], "historical_weather.csv", T0)
        self.save([reading("current", T0 + timedelta(minutes=55), clouds=50)],
                  "historical_weather.csv", T0 + timedelta(hours=1))
        with (self.data_dir / "historical_weather.csv").open("a", encoding="utf-8") as file:
            file.write("not-a-date,40.4169,-3.7035,also-bad,current,,,,,,\n")
        fetch = latest_fetches("current", self.data_dir)[location_key(40.4169, -3.7035)]
        self.assertEqual(fetch.latest_reading.cloud_cover_percent, 50)


if __name__ == "__main__":
    unittest.main()
