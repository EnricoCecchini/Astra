"""Known-value checks for historical weather analytics."""

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import pandas as pd

from weather_app.analytics import (PARTS, hourly_scores, load_weather_history,
                                   nighttime_ranking)


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
