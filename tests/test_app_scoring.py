"""Exercise score display and persistence through Streamlit with fixed forecasts."""

import csv
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from weather_app.client import WeatherError, WeatherReading
from weather_app.astronomy import EPHEMERIS_DIR, EPHEMERIS_FILE
from weather_app.models import AstroSuitabilityScorer

APP = str(Path(__file__).resolve().parents[1] / "app.py")
WHEN = datetime(2026, 11, 15, 21, tzinfo=timezone.utc)


def reading(timestamp, kind="forecast", latitude=40.4, longitude=-3.7):
    return WeatherReading(
        latitude=latitude, longitude=longitude, timestamp=timestamp,
        kind=kind, temperature_c=12, cloud_cover_percent=10,
        humidity_percent=40, visibility_m=10000, wind_speed_mps=2,
        description="clear sky",
    )


@unittest.skipUnless((EPHEMERIS_DIR / EPHEMERIS_FILE).exists(),
                     "Run the app once to cache the astronomy ephemeris")
class AppScoringTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()  # cached readings would otherwise leak between tests
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name) / "scores.csv"
        readings = [reading(WHEN + timedelta(hours=i)) for i in range(0, 51, 3)]
        original_append = AstroSuitabilityScorer.append_score
        stack = ExitStack()
        self.addCleanup(stack.close)
        clock = stack.enter_context(patch("weather_app.planner.datetime", wraps=datetime))
        clock.now.return_value = WHEN
        stack.enter_context(patch("weather_app.client.OpenWeatherClient.forecast", return_value=readings))
        self.current = stack.enter_context(patch(
            "weather_app.client.OpenWeatherClient.current_weather", return_value=reading(WHEN, "current")))
        self.city = stack.enter_context(patch(
            "weather_app.client.OpenWeatherClient.current_weather_for_city",
            return_value=reading(WHEN, "current", 37.18, -3.60)))
        stack.enter_context(patch("weather_app.client.get_api_key", return_value="test-key"))
        stack.enter_context(patch.object(
            AstroSuitabilityScorer, "append_score", autospec=True,
            side_effect=lambda scorer, result: original_append(scorer, result, self.output)))

    def saved_rows(self):
        with self.output.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def test_visible_sites_show_and_save_real_scores(self):
        self.check_search(100, 3)

    def test_no_distance_preference_returns_all_ten_sites(self):
        self.check_search(None, 10)

    def check_search(self, distance, expected_sites):
        app = AppTest.from_file(APP, default_timeout=60)
        app.session_state["user_location"] = (40.4169, -3.7035)
        app.session_state["sites_query"] = ("Saturn", distance)
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        scores = [metric.value for metric in app.metric if metric.label == "Score"]
        self.assertEqual(len(scores), expected_sites)
        self.assertIn("No preference", app.selectbox[1].options)
        self.assertTrue(all(value.endswith("/100") for value in scores),
                        (scores, [warning.value for warning in app.warning]))
        values = [int(value.split("/")[0]) for value in scores]
        self.assertEqual(values, sorted(values, reverse=True))
        rows = self.saved_rows()
        self.assertEqual(len(rows), len(scores))
        self.assertEqual(len({row["site_id"] for row in rows}), len(scores))
        self.assertTrue(all(0 <= float(row["combined"]) <= 100 for row in rows))
        self.assertTrue(all(row["computed_at"] for row in rows))

    def test_reruns_do_not_log_duplicate_scores(self):
        app = AppTest.from_file(APP, default_timeout=60)
        app.session_state["user_location"] = (40.4169, -3.7035)
        app.session_state["sites_query"] = ("Saturn", 100)
        app.run()
        app.selectbox[0].set_value("Mars").run()  # any widget interaction reruns the script
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(len(self.saved_rows()), 3)

    def test_current_conditions_shown_for_shared_location(self):
        app = AppTest.from_file(APP, default_timeout=60)
        app.session_state["user_location"] = (40.4169, -3.7035)
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        labels = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(labels["Temperature"], "12.0 °C")
        self.assertEqual(labels["Visibility"], "10.0 km")
        self.current.assert_called_once()

    def test_city_fallback_sets_location(self):
        app = AppTest.from_file(APP, default_timeout=60).run()
        self.assertTrue(any("enter a city" in item.value for item in app.info))
        app.sidebar.text_input[0].input("Granada")
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state["user_location"], (37.18, -3.60))
        self.assertTrue(any("Granada" in item.value for item in app.subheader))

    def test_city_errors_are_shown_without_crashing(self):
        self.city.side_effect = WeatherError("No city called 'Atlantis' was found. Check the spelling.")
        app = AppTest.from_file(APP, default_timeout=60).run()
        app.sidebar.text_input[0].input("Atlantis")
        app.sidebar.button[0].click().run()
        app.sidebar.text_input[0].input("12345")
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception, str(app.exception))
        errors = [item.value for item in app.sidebar.error]
        self.assertTrue(any("must start with a letter" in error for error in errors), errors)
        self.assertNotIn("user_location", app.session_state)
