"""Finding observing sites from which a chosen celestial body can be seen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
from skyfield import almanac
from skyfield.api import load as skyfield_load
from skyfield.api import wgs84
from skyfield.jpllib import SpiceKernel

from .models import Site

DEFAULT_MIN_ALTITUDE_DEG = 10.0  # low targets are lost in haze, hills and buildings
DEFAULT_MAX_SUN_ALTITUDE_DEG = -6.0  # end of civil twilight: bright planets start to show
LOOKAHEAD_HOURS = 48  # how far ahead to search for the next viewing window
STEP_MINUTES = 5  # time resolution of that search


@dataclass(frozen=True)
class SiteVisibility:
    """A site within range: when the body can be seen from it and where to look.

    Altitude, azimuth and Sun altitude are for the start of the viewing window
    (or for now, if there is no window in the look-ahead period).
    """

    site: Site
    distance_km: float
    visible_now: bool
    window_start_utc: datetime | None  # None: not visible within LOOKAHEAD_HOURS
    window_end_utc: datetime | None  # None: still visible at the end of the look-ahead
    altitude_deg: float
    azimuth_deg: float
    sun_altitude_deg: float
    sunset_utc: datetime | None  # sunset that starts the current or coming night


class Planner:
    """Matches observing sites against a user's location, distance limit and target."""

    def __init__(
        self,
        sites: list[Site],
        celestial_bodies: dict[str, dict],
        ephemeris: SpiceKernel,
        min_altitude_deg: float = DEFAULT_MIN_ALTITUDE_DEG,
        max_sun_altitude_deg: float = DEFAULT_MAX_SUN_ALTITUDE_DEG,
    ):
        self.sites = sites
        self.celestial_bodies = celestial_bodies
        self.min_altitude_deg = min_altitude_deg
        self.max_sun_altitude_deg = max_sun_altitude_deg
        self._earth = ephemeris["earth"]
        self._sun = ephemeris["sun"]
        self._timescale = skyfield_load.timescale()

    def sites_within(self, origin_lat: float, origin_lon: float, max_distance_km: float):
        """Sites no further than ``max_distance_km`` from the origin, nearest first."""
        in_range = [(site, site.distance_km(origin_lat, origin_lon)) for site in self.sites]
        in_range = [(site, d) for site, d in in_range if d <= max_distance_km]
        return sorted(in_range, key=lambda pair: pair[1])

    def sunset_for(self, site: Site, when: datetime) -> datetime | None:
        """Sunset that starts the night around ``when``, in UTC.

        Searches from 12 hours before ``when``: during the day this finds the
        coming sunset, and at night the sunset that started the current night.
        Returns None if the Sun does not set in that window (polar regions).
        """
        observer = self._observer(site)
        start = self._timescale.from_datetime(when - timedelta(hours=12))
        times, _ = almanac.find_settings(observer, self._sun, start, start + 1)
        return times[0].utc_datetime() if len(times) else None

    def _observer(self, site: Site):
        return self._earth + wgs84.latlon(
            site.latitude, site.longitude, elevation_m=site.elevation_m
        )

    def site_outlooks(
        self,
        body_name: str,
        origin_lat: float,
        origin_lon: float,
        max_distance_km: float,
        when: datetime | None = None,
    ) -> list[SiteVisibility]:
        """Every site within range, with when ``body_name`` can next be seen from it.

        A body counts as visible when it is at least ``min_altitude_deg`` above
        the horizon and, except for the Moon, the Sun is at or below
        ``max_sun_altitude_deg``. Weather is not considered here.

        The next ``LOOKAHEAD_HOURS`` from ``when`` (default: now) are sampled
        every ``STEP_MINUTES``; the first visible stretch becomes the site's
        viewing window. Sites are ordered: visible now, then by window start
        (sites with no window last), then by distance.
        """
        if body_name not in self.celestial_bodies:
            raise ValueError(f"Unknown celestial body: {body_name!r}")
        if max_distance_km <= 0:
            raise ValueError("max_distance_km must be positive")

        body = self.celestial_bodies[body_name]
        needs_darkness = body["kind"] != "moon"  # the Moon is easy to see in daylight
        when = when or datetime.now(timezone.utc)
        if when.tzinfo is None:
            raise ValueError("when must be timezone-aware (e.g. UTC)")

        offsets = np.arange(0, LOOKAHEAD_HOURS * 60 + 1, STEP_MINUTES)
        sample_times = [when + timedelta(minutes=int(m)) for m in offsets]
        t = self._timescale.from_datetimes(sample_times)

        results = []
        for site, distance in self.sites_within(origin_lat, origin_lon, max_distance_km):
            at_site = self._observer(site).at(t)
            alt, az, _ = at_site.observe(body["target"]).apparent().altaz()
            sun_alt, _, _ = at_site.observe(self._sun).apparent().altaz()

            visible = alt.degrees >= self.min_altitude_deg
            if needs_darkness:
                visible &= sun_alt.degrees <= self.max_sun_altitude_deg

            start_i = int(np.argmax(visible)) if visible.any() else None
            end_i = None
            if start_i is not None:
                after = np.flatnonzero(~visible[start_i:])
                end_i = start_i + int(after[0]) if len(after) else None
            look_i = start_i if start_i is not None else 0  # where to look on arrival

            results.append(
                SiteVisibility(
                    site=site,
                    distance_km=round(distance, 1),
                    visible_now=bool(visible[0]),
                    window_start_utc=sample_times[start_i] if start_i is not None else None,
                    window_end_utc=sample_times[end_i] if end_i is not None else None,
                    altitude_deg=round(float(alt.degrees[look_i]), 1),
                    azimuth_deg=round(float(az.degrees[look_i]), 1),
                    sun_altitude_deg=round(float(sun_alt.degrees[look_i]), 1),
                    sunset_utc=self.sunset_for(site, when),
                )
            )

        never = when + timedelta(days=365)
        return sorted(
            results,
            key=lambda r: (not r.visible_now, r.window_start_utc or never, r.distance_km),
        )

    def visible_sites(self, *args, **kwargs) -> list[SiteVisibility]:
        """Only the sites from :meth:`site_outlooks` where the body is visible now."""
        return [r for r in self.site_outlooks(*args, **kwargs) if r.visible_now]
