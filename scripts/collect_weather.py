"""Collect current and forecast weather every five minutes until stopped."""

import argparse
import logging
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from weather_app.client import OpenWeatherClient, WeatherError
from weather_app.sites import load_sites

logger = logging.getLogger("weather_collector")


def collect_once(client, sites):
    """Keep collecting other sites/endpoints if an individual request fails."""
    successes = 0
    for site in sites:
        for name, fetch in (("current", client.current_weather), ("forecast", client.forecast)):
            try:
                result = fetch(site.latitude, site.longitude)
            except (WeatherError, ValueError) as exc:
                logger.warning("%s %s failed: %s", site.site_id, name, exc)
                continue
            successes += 1
            count = len(result) if isinstance(result, list) else 1
            logger.info("%s %s: appended %d readings", site.site_id, name, count)
    logger.info("Collection complete: %d/%d successful requests", successes, len(sites) * 2)
    return successes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=float, default=300, help="Seconds between collection starts (default: 300)")
    parser.add_argument("--once", action="store_true", help="Run one collection and exit")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Collector started: interval=%s seconds", args.interval)
    try:
        while True:
            started = time.monotonic()
            try:
                collect_once(OpenWeatherClient(), load_sites())
            except (ValueError, OSError) as exc:
                logger.error("Collection could not start: %s", exc)
            if args.once:
                return
            delay = max(0, args.interval - (time.monotonic() - started))
            logger.info("Next collection in %.1f seconds", delay)
            time.sleep(delay)
    except KeyboardInterrupt:
        logger.info("Collector stopped")


if __name__ == "__main__":
    main()
