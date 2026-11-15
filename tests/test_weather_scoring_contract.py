"""Check that normalized weather feeds the scorer and reproduces its sample."""
import csv
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch
from tempfile import TemporaryDirectory

from weather_app.client import OpenWeatherClient
from weather_app.models import AstroSuitabilityScorer


class WeatherScoringContractTests(unittest.TestCase):
    @patch("weather_app.client.requests.get")
    def test_api_response_through_scorer_matches_sample_csv(self, get):
        sample_path = Path(__file__).resolve().parents[1] / "data" / "scoring_output.csv"
        with sample_path.open(newline="", encoding="utf-8") as file:
            sample = next(csv.DictReader(file))
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
        reading = OpenWeatherClient(api_key="test-key").forecast(40.4169, -3.7035)[0]
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
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
                self.assertAlmostEqual(getattr(score, field), float(sample[field]), places=6)


if __name__ == "__main__":
    unittest.main()
