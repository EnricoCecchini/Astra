"""Append normalized API readings to local weather history."""

import csv
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def append_weather(readings, path: Path) -> None:
    """Append a batch, retaining both fetch time and observation/forecast time."""
    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for reading in readings:
        row = {"fetched_at": fetched_at, **asdict(reading)}
        row["timestamp"] = reading.timestamp.isoformat()
        rows.append(row)
    if not rows:
        return
    columns = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_newline = False
    if path.exists() and path.stat().st_size:
        with path.open(newline="", encoding="utf-8") as file:
            if next(csv.reader(file), None) != columns:
                raise ValueError("Weather CSV header does not match weather reading columns")
        with path.open("rb") as file:
            file.seek(-1, 2)
            needs_newline = file.read(1) not in (b"\n", b"\r")
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        if file.tell() == 0:
            writer.writeheader()
        elif needs_newline:
            file.write("\n")
        writer.writerows(rows)
