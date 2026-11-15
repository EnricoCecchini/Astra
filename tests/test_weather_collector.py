"""The periodic collector: per-request resilience, skipping, and the app's thread."""

import os
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.collect_weather import collect_once
from weather_app import collector
from weather_app.client import WeatherError, WeatherReading
from weather_app.storage import append_weather


class WeatherCollectorTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data_dir = Path(temporary.name)

    def save_current(self, fetched_at):
        reading = WeatherReading(40.4, -3.7, fetched_at, "current", 12., 10., 40., 10000., 2., "clear")
        with patch("weather_app.storage.datetime") as clock:
            clock.now.return_value = fetched_at
            append_weather([reading], self.data_dir / "historical_weather.csv")

    def test_failed_current_request_still_collects_forecast_and_other_sites(self):
        client = Mock()
        client.current_weather.side_effect = [WeatherError("Service unavailable"), object()]
        client.forecast.return_value = [object(), object()]
        sites = [SimpleNamespace(site_id="one", latitude=40, longitude=-3),
                 SimpleNamespace(site_id="two", latitude=41, longitude=-4)]
        with self.assertLogs("weather_collector", level="INFO") as messages:
            self.assertEqual(collect_once(client, sites), 3)
        self.assertEqual(client.current_weather.call_count, 2)
        self.assertEqual(client.forecast.call_count, 2)
        self.assertTrue(any("3/4 successful" in message for message in messages.output))

    def test_recently_collected_uses_latest_saved_fetch(self):
        self.assertIsNone(collector.last_collected(self.data_dir))
        self.assertFalse(collector.recently_collected(300, self.data_dir))
        now = datetime.now(timezone.utc)
        self.save_current(now - timedelta(minutes=10))
        self.assertFalse(collector.recently_collected(300, self.data_dir))
        self.save_current(now - timedelta(minutes=2))
        self.assertTrue(collector.recently_collected(300, self.data_dir))
        self.assertEqual(collector.last_collected(self.data_dir), now - timedelta(minutes=2))

    def run_rounds(self, client_factory, rounds=1):
        """Run run_forever for a fixed number of rounds without real waiting."""
        stop = threading.Event()
        waits = []

        def wait(_seconds):
            waits.append(_seconds)
            if len(waits) >= rounds:
                stop.set()

        stop.wait = wait
        sites = [SimpleNamespace(site_id="one", latitude=40, longitude=-3)]
        collector.run_forever(300, stop, self.data_dir, client_factory, lambda: sites)
        return waits

    def test_round_collects_into_the_given_data_dir(self):
        client = Mock()
        client.forecast.return_value = []
        factory = Mock(return_value=client)
        with self.assertLogs("weather_collector", level="INFO"):
            waits = self.run_rounds(factory)
        factory.assert_called_once_with(data_dir=self.data_dir)
        client.current_weather.assert_called_once_with(40, -3)
        self.assertTrue(0 < waits[0] <= 300)

    def test_round_is_skipped_when_data_is_recent(self):
        self.save_current(datetime.now(timezone.utc))
        factory = Mock()
        with self.assertLogs("weather_collector", level="INFO") as messages:
            self.run_rounds(factory)
        factory.assert_not_called()
        self.assertTrue(any("Skipping collection" in message for message in messages.output))

    def test_errors_do_not_stop_the_loop(self):
        factory = Mock(side_effect=[ValueError("Set OPENWEATHER_API_KEY"), RuntimeError("boom")])
        with self.assertLogs("weather_collector", level="INFO") as messages:
            self.run_rounds(factory, rounds=2)
        self.assertEqual(factory.call_count, 2)
        self.assertTrue(any("could not start" in message for message in messages.output))
        self.assertTrue(any("Unexpected error" in message for message in messages.output))

    def test_invalid_interval_is_rejected(self):
        with self.assertRaises(ValueError):
            collector.run_forever(0)

    def test_background_thread_starts_once_and_can_be_disabled(self):
        release = threading.Event()
        self.addCleanup(release.set)
        with (patch.dict(os.environ, {collector.DISABLE_ENV: ""}),
              patch.object(collector, "run_forever", side_effect=lambda *_: release.wait(5)) as loop):
            first = collector.start_background()
            second = collector.start_background()
            self.assertIs(first, second)
            self.assertTrue(first.daemon)
            self.assertEqual(first.name, collector.THREAD_NAME)
            self.assertIs(collector.running_thread(), first)
            loop.assert_called_once_with(collector.DEFAULT_INTERVAL_S)
        release.set()
        first.join(5)
        self.assertIsNone(collector.running_thread())
        with patch.dict(os.environ, {collector.DISABLE_ENV: "off"}):
            self.assertIsNone(collector.start_background())
