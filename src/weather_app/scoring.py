"""Observation suitability scores.

PLACEHOLDER: real per-site scoring is not implemented yet. Until it is, the app
shows the single sample row in ``data/scoring_output.csv`` for every site so the
results table has its final shape.
"""

from __future__ import annotations

import csv
from pathlib import Path

SAMPLE_SCORES_CSV = Path(__file__).resolve().parents[2] / "data" / "scoring_output.csv"


def load_sample_scores(path: Path = SAMPLE_SCORES_CSV) -> dict[str, float]:
    """Return the first row of the sample scoring output as {component: score}."""
    with open(path, newline="", encoding="utf-8") as file:
        row = next(csv.DictReader(file))
    return {key: float(value) for key, value in row.items() if key != "timestamp"}
