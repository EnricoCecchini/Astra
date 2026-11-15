"""Exercise the Live Conditions view on saved (collected) data through Streamlit."""

import csv
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from weather_app.astronomy import EPHEMERIS_DIR, EPHEMERIS_FILE
from weather_app.client import Place, WeatherError, WeatherReading
from weather_app.history import SavedFetch, location_key
from weather_app.models import AstroSuitabilityScorer
from weather_app.sites import load_sites

APP = str(Path(__file__).resolve().parents[1] / "app.py")
WHEN = datetime(2026, 11, 15, 21, tzinfo=timezone.utc)


def reading(site, timestamp, kind):
    return WeatherReading(
        latitude=site.latitude, longitude=site.longitude, timestamp=timestamp,
        kind=kind, temperature_c=12, cloud_cover_percent=10,
        humidity_percent=40, visibility_m=10000, wind_speed_mps=2,
        description="clear sky",
    )


def saved_data(fetched_at):
    """What the collector would have saved: one current and one forecast batch per site."""
    sites = load_sites()
    return {
        "current": {location_key(s.latitude, s.longitude):
                    SavedFetch(fetched_at, (reading(s, fetched_at, "current"),)) for s in sites},
        "forecast": {location_key(s.latitude, s.longitude):
                     SavedFetch(fetched_at, tuple(reading(s, WHEN + timedelta(hours=h), "forecast")
                                                  for h in range(0, 51, 3))) for s in sites},
    }


@unittest.skipUnless((EPHEMERIS_DIR / EPHEMERIS_FILE).exists(),
                     "Run the app once to cache the astronomy ephemeris")
class AppScoringTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()  # cached data would otherwise leak between tests
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.output = Path(directory.name) / "scores.csv"
        self.saved = saved_data(WHEN - timedelta(minutes=10))
        original_append = AstroSuitabilityScorer.append_score
        stack = ExitStack()
        self.addCleanup(stack.close)
        clock = stack.enter_context(patch("weather_app.planner.datetime", wraps=datetime))
        clock.now.return_value = WHEN
        stack.enter_context(patch("weather_app.history.latest_fetches",
                                  side_effect=lambda kind: self.saved[kind]))
        # Any weather request from the app would be a bug: only the collector fetches.
        self.http = stack.enter_context(patch(
            "weather_app.client.requests.get", side_effect=AssertionError("the app must not fetch")))
        self.geocode = stack.enter_context(patch(
            "weather_app.client.OpenWeatherClient.geocode_city",
            return_value=Place("Granada", 37.18, -3.60, "ES")))
        stack.enter_context(patch("weather_app.client.get_api_key", return_value="test-key"))
        # The real background collector would call the API and write to data/.
        self.start_collector = stack.enter_context(patch(
            "weather_app.collector.start_background", return_value=None))
        stack.enter_context(patch.object(
            AstroSuitabilityScorer, "append_score", autospec=True,
            side_effect=lambda scorer, result: original_append(scorer, result, self.output)))

    def saved_rows(self):
        with self.output.open(newline="", encoding="utf-8") as file:
            return list(csv.DictReader(file))

    def search(self, distance=100, body="Saturn"):
        app = AppTest.from_file(APP, default_timeout=60)
        app.session_state["user_location"] = (40.4169, -3.7035)
        app.session_state["sites_query"] = (body, distance)
        return app.run()

    def test_visible_sites_show_and_save_real_scores(self):
        self.check_search(100, 3)

    def test_no_distance_preference_returns_all_ten_sites(self):
        self.check_search(None, 10)

    def check_search(self, distance, expected_sites):
        app = self.search(distance)
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
        self.http.assert_not_called()

    def test_reruns_do_not_log_duplicate_scores(self):
        app = self.search(100)
        app.selectbox[0].set_value("Mars").run()  # any widget interaction reruns the script
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(len(self.saved_rows()), 3)
        self.http.assert_not_called()

    def test_site_without_saved_forecast_explains_how_to_get_one(self):
        del self.saved["forecast"][location_key(40.4169, -3.7035)]  # Madrid centre
        app = self.search(100)
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any("no forecast has been recorded" in item.value for item in app.warning))
        self.assertEqual(len(self.saved_rows()), 2)

    def test_current_conditions_come_from_nearest_saved_site(self):
        app = AppTest.from_file(APP, default_timeout=60)
        app.session_state["user_location"] = (40.42, -3.70)
        app.run()
        self.assertFalse(app.exception, str(app.exception))
        labels = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(labels["Temperature"], "12.0 °C")
        self.assertEqual(labels["Visibility"], "10.0 km")
        self.assertTrue(any("Madrid (Puerta del Sol)" in item.value for item in app.caption))
        self.http.assert_not_called()

    def test_no_saved_data_points_to_the_collector(self):
        self.saved = {"current": {}, "forecast": {}}
        app = self.search(100)
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any("No current conditions have been recorded" in item.value for item in app.info))
        self.assertFalse(self.output.exists())

    def test_city_fallback_sets_location_without_fetching_weather(self):
        app = AppTest.from_file(APP, default_timeout=60).run()
        self.assertTrue(any("enter a city" in item.value for item in app.info))
        app.sidebar.text_input[0].input("Granada")
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertEqual(app.session_state["user_location"], (37.18, -3.60))
        self.assertTrue(any("Granada, ES" in item.value for item in app.subheader))
        self.geocode.assert_called_once_with("Granada")
        self.http.assert_not_called()

    def test_app_starts_the_background_collector(self):
        app = AppTest.from_file(APP, default_timeout=60).run()
        self.assertFalse(app.exception, str(app.exception))
        self.start_collector.assert_called_once_with()
        self.assertTrue(any("collection is off" in item.value for item in app.sidebar.caption))

    def test_city_errors_are_shown_without_crashing(self):
        self.geocode.side_effect = WeatherError("No city called 'Atlantis' was found. Check the spelling.")
        app = AppTest.from_file(APP, default_timeout=60).run()
        app.sidebar.text_input[0].input("Atlantis")
        app.sidebar.button[0].click().run()
        self.assertTrue(any("Atlantis" in error.value for error in app.sidebar.error))
        app.sidebar.text_input[0].input("12345")
        app.sidebar.button[0].click().run()
        self.assertFalse(app.exception, str(app.exception))
        errors = [item.value for item in app.sidebar.error]
        self.assertTrue(any("must start with a letter" in error for error in errors), errors)
        self.assertNotIn("user_location", app.session_state)
