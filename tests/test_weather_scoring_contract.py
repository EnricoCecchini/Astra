"""Check that normalized weather feeds the scorer and reproduces a fixed sample."""
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory

from weather_app.client import OpenWeatherClient
from weather_app.models import AstroSuitabilityScorer

# Fixed reference entry: the scorer's output for the inputs below (cloud 10 %,
# humidity 40 %, visibility 10 km, wind 2 m/s, altitude 60 deg, darkness 95,
# moonlight 80). Kept here so the check never depends on the live scoring log.
SAMPLE = {
    "timestamp": "2026-11-14T22:00:00+01:00",
    "cloud": 90.0, "humidity": 60.0, "visibility": 100.0, "wind": 80.0,
    "altitude": 100.0, "darkness": 95.0, "moonlight": 80.0,
    "weather": 84.0, "astronomical": 94.5, "combined": 88.2,
}


class WeatherScoringContractTests(unittest.TestCase):
    @patch("weather_app.client.requests.get")
    def test_api_response_through_scorer_matches_fixed_sample(self, get):
        sample = SAMPLE
        timestamp = datetime.fromisoformat(sample["timestamp"])
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "dt": timestamp.timestamp(),
            "main": {"temp": 12.0, "humidity": 40},
            "clouds": {"all": 10},
            "visibility": 10000,
            "wind": {"speed": 2},
            "weather": [{"description": "clear sky"}],
        }
        get.return_value = response
        # Exercise the forecast endpoint's list structure and normalization.
        response.json.return_value = {"list": [response.json.return_value]}
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        reading = OpenWeatherClient(api_key="test-key", data_dir=temporary.name).forecast(40.4169, -3.7035)[0]
        score = AstroSuitabilityScorer(output_path=Path(temporary.name) / "scores.csv").score(
            site_id="test-site",
            timestamp=reading.timestamp,
            cloud_cover_percent=reading.cloud_cover_percent,
            relative_humidity_percent=reading.humidity_percent,
            visibility_m=reading.visibility_m,
            wind_speed_mps=reading.wind_speed_mps,
            altitude_degrees=60,
            darkness_suitability=95,
            moonlight_suitability=80,
        )
        self.assertEqual(score.timestamp, timestamp)
        for field in ("cloud", "humidity", "visibility", "wind", "altitude", "darkness", "moonlight", "weather", "astronomical", "combined"):
            with self.subTest(field=field):
                self.assertAlmostEqual(getattr(score, field), sample[field], places=6)


if __name__ == "__main__":
    unittest.main()
