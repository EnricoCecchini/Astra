"""Collect current and forecast weather every five minutes until stopped.

The Streamlit app already runs this collection in a background thread while it
is open. Use this script to keep collecting when the app is not running. Rounds
are skipped while recent data exists, so running both does not duplicate rows.
"""

import argparse
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weather_app.client import OpenWeatherClient
from weather_app.collector import DEFAULT_INTERVAL_S, collect_once, logger, run_forever
from weather_app.sites import load_sites

__all__ = ["collect_once", "main"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                        help=f"Seconds between collection starts (default: {DEFAULT_INTERVAL_S})")
    parser.add_argument("--once", action="store_true", help="Run one collection now and exit")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.once:
        try:
            collect_once(OpenWeatherClient(), load_sites())
        except (ValueError, OSError) as exc:
            logger.error("Collection could not start: %s", exc)
        return
    try:
        run_forever(args.interval)
    except KeyboardInterrupt:
        logger.info("Collector stopped")


if __name__ == "__main__":
    main()
