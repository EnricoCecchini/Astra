"""Known-value checks for historical weather analytics."""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import pandas as pd

from weather_app.analytics import (PARTS, hourly_scores, load_weather_history,
                                   nighttime_ranking, ranking_chart, heatmap_chart,
                                   components_chart, history_chart, forecast_chart)


class WeatherAnalyticsTests(unittest.TestCase):
    def test_hourly_average_and_night_ranking(self):
        frame = pd.DataFrame({"site": ["A", "A", "A", "B"],
            "local_time": pd.to_datetime(["2026-11-15T20:00Z", "2026-11-15T20:05Z",
                                           "2026-11-15T12:00Z", "2026-11-15T20:00Z"]),
            "weather": [100., 50., 0., 80.], "is_night": [True, True, False, True]})
        hourly = hourly_scores(frame)
        self.assertEqual(hourly[(hourly.site == "A") & (hourly.local_time.dt.hour == 20)].weather.iloc[0], 75)
        ranking = nighttime_ranking(frame)
        self.assertEqual(list(ranking.site), ["B", "A"])
        self.assertEqual(list(ranking.n), [1, 2])
        self.assertEqual(list(ranking.above_75), [100, 50])

    def test_observation_deduplication_and_weighted_parts(self):
        site = SimpleNamespace(site_id="test", name="Test site", latitude=40., longitude=-3.)
        row = dict(fetched_at="2026-11-15T20:00:00Z", timestamp="2026-11-15T19:55:00Z",
                   latitude=40, longitude=-3, kind="current", cloud_cover_percent=10,
                   humidity_percent=40, visibility_m=10000, wind_speed_mps=2)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "weather.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
                writer.writerow({**row, "fetched_at": "2026-11-15T20:05:00Z"})
            frame = load_weather_history(path, [site], "current")
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.site_id.iloc[0], "test")
        self.assertAlmostEqual(frame.weather.iloc[0], 84)
        self.assertAlmostEqual(frame[list(PARTS.values())].sum(axis=1).iloc[0], 84)

    def test_chart_structure_and_unobserved_heatmap_hours(self):
        frame = pd.DataFrame({"site": ["A", "B"],
            "local_time": pd.to_datetime(["2026-11-15T20:00Z", "2026-11-15T20:00Z"]),
            "timestamp": pd.to_datetime(["2026-11-15T20:00Z", "2026-11-15T20:00Z"]),
            "weather": [84., 30.], "is_night": [True, True],
            "cloud_part": [45., 10.], "humidity_part": [12., 5.],
            "visibility_part": [15., 10.], "wind_part": [12., 5.]})
        history = history_chart(frame, "UTC")
        self.assertEqual(len(history.data), 2)
        self.assertTrue(any(shape.y0 == 75 for shape in history.layout.shapes))
        ranked = ranking_chart(frame)
        self.assertEqual(list(ranked.data[0].y), ["A", "B"])
        self.assertIn("100% >75", ranked.data[0].text[0])
        heatmap = heatmap_chart(frame, "UTC")
        self.assertEqual(len(heatmap.data[0].x), 14)
        self.assertTrue(pd.isna(heatmap.data[0].z[0][0]))
        parts = components_chart(frame)
        self.assertEqual(len(parts.data), 4)
        self.assertAlmostEqual(sum(trace.x[0] for trace in parts.data), 84)
        track = pd.DataFrame({"local_time": pd.date_range("2026-11-15T20:00Z", periods=2, freq="5min"),
            "altitude": [30., 35.], "weather": [84., 85.], "dark_enough": [True, True]})
        forecast = forecast_chart(track, "A", "UTC", 10)
        self.assertEqual(forecast.data[1].yaxis, "y2")
        self.assertTrue(forecast.layout.shapes)

    def test_forecast_uses_only_latest_issue(self):
        site = SimpleNamespace(site_id="test", name="Test", latitude=40., longitude=-3.)
        row = dict(fetched_at="2026-11-15T12:00Z", timestamp="2026-11-15T21:00Z",
                   latitude=40, longitude=-3, kind="forecast", cloud_cover_percent=10,
                   humidity_percent=40, visibility_m=10000, wind_speed_mps=2)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "forecast.csv"
            with path.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=list(row))
                writer.writeheader()
                writer.writerow(row)
                writer.writerow({**row, "timestamp": "2026-11-16T00:00Z"})
                writer.writerow({**row, "fetched_at": "2026-11-15T12:05Z", "cloud_cover_percent": 100})
            frame = load_weather_history(path, [site], "forecast")
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.cloud_cover_percent.iloc[0], 100)
