"""Periodic weather collection: the only code that requests weather from the API.

The Streamlit app starts it in a background thread (``start_background``) and
``scripts/collect_weather.py`` runs the same loop from a terminal. Each round
saves current weather and the forecast for every site through
``OpenWeatherClient``, which appends them to the CSV history.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .client import OpenWeatherClient, WeatherError
from .history import latest_fetches
from .sites import load_sites
from .storage import DATA_DIR

logger = logging.getLogger("weather_collector")

DEFAULT_INTERVAL_S = 300
THREAD_NAME = "weather-collector"
# Set WEATHER_COLLECTOR=off to keep the app from starting the background thread
# (the tests do this so they never call the real API or touch data/).
DISABLE_ENV = "WEATHER_COLLECTOR"

_start_lock = threading.Lock()


def collect_once(client, sites) -> int:
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


def last_collected(data_dir: str | Path = DATA_DIR) -> datetime | None:
    """When current weather was last saved for any location, or None if never."""
    fetches = latest_fetches("current", data_dir)
    return max((fetch.fetched_at for fetch in fetches.values()), default=None)


def recently_collected(interval_s: float, data_dir: str | Path = DATA_DIR) -> bool:
    """True if another collector (or an earlier run) saved data within the interval.

    Skipping such rounds keeps the app's thread and a terminal collector from
    saving the same weather twice.
    """
    last = last_collected(data_dir)
    if last is None:
        return False
    # 10% slack so a collector running on the same schedule is not skipped by jitter.
    return datetime.now(timezone.utc) - last < timedelta(seconds=interval_s * 0.9)


def run_forever(interval_s: float = DEFAULT_INTERVAL_S, stop: threading.Event | None = None,
                data_dir: str | Path = DATA_DIR, client_factory=OpenWeatherClient,
                sites_loader=load_sites) -> None:
    """Collect every ``interval_s`` seconds until ``stop`` is set."""
    if interval_s <= 0:
        raise ValueError("interval_s must be positive")
    stop = stop or threading.Event()
    logger.info("Collector started: interval=%s seconds", interval_s)
    while not stop.is_set():
        started = time.monotonic()
        try:
            if recently_collected(interval_s, data_dir):
                logger.info("Skipping collection: data was saved less than one interval ago")
            else:
                collect_once(client_factory(data_dir=data_dir), sites_loader())
        except (ValueError, OSError) as exc:  # e.g. missing API key, unreadable sites.csv
            logger.error("Collection could not start: %s", exc)
        except Exception:  # noqa: BLE001 - a background loop must survive any one bad round
            logger.exception("Unexpected error during collection; retrying next interval")
        stop.wait(max(0.0, interval_s - (time.monotonic() - started)))
    logger.info("Collector stopped")


def running_thread() -> threading.Thread | None:
    """The live background collector thread of this process, if any."""
    return next((thread for thread in threading.enumerate()
                 if thread.name == THREAD_NAME and thread.is_alive()), None)


def start_background(interval_s: float = DEFAULT_INTERVAL_S) -> threading.Thread | None:
    """Start the collector in a daemon thread, once per process.

    The thread is found by name rather than a module variable, so Streamlit
    reruns and code reloads never start a second one. Returns None when
    disabled with ``WEATHER_COLLECTOR=off``.
    """
    if os.environ.get(DISABLE_ENV, "").strip().lower() == "off":
        return None
    with _start_lock:
        thread = running_thread()
        if thread is None:
            if not logger.handlers:  # show progress in the terminal running Streamlit
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
                logger.addHandler(handler)
                logger.setLevel(logging.INFO)
                logger.propagate = False
            thread = threading.Thread(target=run_forever, args=(interval_s,),
                                      name=THREAD_NAME, daemon=True)
            thread.start()
        return thread
