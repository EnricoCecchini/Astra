"""Exercise all analytics views without changing the real CSV histories."""

from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from weather_app.astronomy import EPHEMERIS_DIR, EPHEMERIS_FILE
from weather_app.sites import load_sites


@unittest.skipUnless((EPHEMERIS_DIR / EPHEMERIS_FILE).exists(), "Astronomy ephemeris is not cached")
class AnalyticsUiTests(unittest.TestCase):
    def test_all_five_charts_and_empty_site_selection(self):
        sites = load_sites()[:2]
        def row(site, timestamp):
            return {"site_id": site.site_id, "site": site.name,
                    "timestamp": pd.Timestamp(timestamp), "fetched_at": pd.Timestamp.now(tz="UTC"),
                    "weather": 84., "cloud_part": 45., "humidity_part": 12.,
                    "visibility_part": 15., "wind_part": 12.}
        history = pd.DataFrame([row(site, "2026-11-15T21:00Z") for site in sites])
        timestamps = pd.date_range(pd.Timestamp.now(tz="UTC").floor("h"), periods=50, freq="3h")
        forecasts = pd.DataFrame([row(site, timestamp) for site in sites for timestamp in timestamps])
        def load(path, all_sites, kind):
            return (history if kind == "current" else forecasts).copy()
        with (patch("weather_app.analytics_ui.load_weather_history", side_effect=load),
              patch("weather_app.collector.start_background", return_value=None)):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=60).run()
            app.sidebar.radio[0].set_value("Analytics").run()
            self.assertFalse(app.exception, str(app.exception))
            self.assertEqual(len(app.get("plotly_chart")), 5)
            self.assertEqual([tab.label for tab in app.tabs],
                             ["Weather Analytics", "Location Explorer", "Observation Planner"])
            app.multiselect[0].set_value([]).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("Select at least one site" in item.value for item in app.info))
