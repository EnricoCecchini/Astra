"""Persistence checks for scoring history; run with unittest discovery."""

import csv
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from weather_app.models import AstroSuitabilityScorer


class ScoringCsvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history" / "scores.csv"
        self.scorer = AstroSuitabilityScorer(output_path=self.path)
        self.inputs = dict(
            timestamp=datetime(2026, 11, 14, 21, tzinfo=timezone.utc),
            site_id="site-001",
            cloud_cover_percent=10, relative_humidity_percent=40,
            visibility_m=10000, wind_speed_mps=2, altitude_degrees=60,
            darkness_suitability=95, moonlight_suitability=80,
        )
        with patch.object(self.scorer, "append_score"):
            self.result = self.scorer.score(**self.inputs)

    def test_score_automatically_appends_each_result(self):
        first = self.scorer.score(**self.inputs)
        second = self.scorer.score(**{
            **self.inputs, "cloud_cover_percent": 100, "site_id": "site-002"
        })
        with self.path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2)
        self.assertEqual(first.site_id, "site-001")
        self.assertEqual(second.site_id, "site-002")
        self.assertEqual([row["site_id"] for row in rows], ["site-001", "site-002"])
        self.assertEqual(float(rows[0]["combined"]), first.combined)
        self.assertEqual(float(rows[1]["combined"]), second.combined)
        self.assertLess(second.combined, first.combined)

    def test_invalid_score_does_not_create_history(self):
        with self.assertRaises(ValueError):
            self.scorer.score(**{**self.inputs, "cloud_cover_percent": 101})
        self.assertFalse(self.path.exists())

    def test_invalid_site_id_does_not_create_history(self):
        for site_id in ("", "  ", None, 123):
            with self.subTest(site_id=site_id), self.assertRaises(ValueError):
                self.scorer.score(**{**self.inputs, "site_id": site_id})
        self.assertFalse(self.path.exists())

    def test_rating_bands_and_ordering(self):
        with patch.object(self.scorer, "append_score"):
            clear = self.scorer.score(**self.inputs)
            cloudy = self.scorer.score(**{**self.inputs, "cloud_cover_percent": 100,
                                          "site_id": "site-002"})
        self.assertEqual(clear.rating, "Excellent")  # combined 88.2
        self.assertEqual(cloudy.rating, "Good")  # combined 64.2
        self.assertEqual(sorted([clear, cloudy]), [cloudy, clear])
        self.assertIs(max([cloudy, clear]), clear)
        self.assertEqual(str(clear), "site-001: 88/100 (Excellent)")

    def test_computed_at_is_logged_separately_from_observing_time(self):
        self.scorer.score(**self.inputs)
        with self.path.open(newline="", encoding="utf-8") as file:
            row = next(csv.DictReader(file))
        self.assertEqual(row["timestamp"], "2026-11-14T21:00:00+00:00")
        computed_at = datetime.fromisoformat(row["computed_at"])
        self.assertIsNotNone(computed_at.tzinfo)
        self.assertGreater(computed_at, datetime(2026, 1, 1, tzinfo=timezone.utc))

    def test_score_reports_persistence_failure(self):
        with patch.object(self.scorer, "append_score", side_effect=OSError("write failed")):
            with self.assertRaises(OSError):
                self.scorer.score(**self.inputs)

    def test_append_preserves_rows_and_writes_one_header(self):
        self.assertEqual(self.scorer.append_score(self.result, self.path), self.path)
        original = self.path.read_bytes()
        self.scorer.append_score(self.result, str(self.path))
        self.assertTrue(self.path.read_bytes().startswith(original))
        with self.path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(rows[0]["timestamp"], "2026-11-14T21:00:00+00:00")
        self.assertAlmostEqual(float(rows[0]["combined"]), 88.2)

    def test_empty_file_and_missing_final_newline(self):
        self.path.parent.mkdir()
        self.path.touch()
        self.scorer.append_score(self.result, self.path)
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\r\n"))
        self.scorer.append_score(self.result, self.path)
        with self.path.open(newline="", encoding="utf-8") as file:
            self.assertEqual(len(list(csv.DictReader(file))), 2)

    def test_wrong_header_is_rejected_without_changing_file(self):
        self.path.parent.mkdir()
        original = b"timestamp,score\nprevious,42\n"
        self.path.write_bytes(original)
        with self.assertRaises(ValueError):
            self.scorer.append_score(self.result, self.path)
        self.assertEqual(self.path.read_bytes(), original)
