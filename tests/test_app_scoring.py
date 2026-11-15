"""Exercise score display and persistence through Streamlit with fixed forecasts."""

import csv
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from weather_app.client import WeatherReading
from weather_app.astronomy import EPHEMERIS_DIR, EPHEMERIS_FILE
from weather_app.models import AstroSuitabilityScorer


@unittest.skipUnless((EPHEMERIS_DIR / EPHEMERIS_FILE).exists(),
                     "Run the app once to cache the astronomy ephemeris")
class AppScoringTests(unittest.TestCase):
    def test_visible_sites_show_and_save_real_scores(self):
        self.check_search(100, 3)

    def test_no_distance_preference_returns_all_ten_sites(self):
        self.check_search(None, 10)

    def check_search(self, distance, expected_sites):
        when = datetime(2026, 11, 15, 21, tzinfo=timezone.utc)
        readings = [WeatherReading(
            latitude=40.4, longitude=-3.7, timestamp=when + timedelta(hours=i),
            kind="forecast", temperature_c=12, cloud_cover_percent=10,
            humidity_percent=40, visibility_m=10000, wind_speed_mps=2,
            description="clear sky",
        ) for i in range(0, 51, 3)]
        original_append = AstroSuitabilityScorer.append_score
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scores.csv"
            with (
                patch("weather_app.planner.datetime", wraps=datetime) as clock,
                patch("weather_app.client.OpenWeatherClient.forecast", return_value=readings),
                patch("weather_app.client.get_api_key", return_value="test-key"),
                patch.object(AstroSuitabilityScorer, "append_score", autospec=True,
                             side_effect=lambda scorer, result: original_append(scorer, result, output)),
            ):
                clock.now.return_value = when
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60)
                app.session_state["user_location"] = (40.4169, -3.7035)
                app.session_state["sites_query"] = ("Saturn", distance)
                app.run()
            self.assertFalse(app.exception, str(app.exception))
            scores = [metric.value for metric in app.metric if metric.label == "Score"]
            self.assertTrue(scores)
            self.assertEqual(len(scores), expected_sites)
            self.assertIn("No preference", app.selectbox[1].options)
            self.assertTrue(all(value.endswith("/100") for value in scores),
                            (scores, [warning.value for warning in app.warning]))
            with output.open(newline="", encoding="utf-8") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), len(scores))
            self.assertEqual(len({row["site_id"] for row in rows}), len(scores))
            self.assertTrue(all(0 <= float(row["combined"]) <= 100 for row in rows))
