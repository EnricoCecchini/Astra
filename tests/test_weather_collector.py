"""The collector continues through a failed endpoint without losing other sites."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.collect_weather import collect_once
from weather_app.client import WeatherError


class WeatherCollectorTests(unittest.TestCase):
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
