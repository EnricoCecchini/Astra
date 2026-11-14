"""Finding observing sites from which a chosen celestial body can be seen."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from skyfield.api import load as skyfield_load
from skyfield.api import wgs84
from skyfield.jpllib import SpiceKernel

from .models import Site

DEFAULT_MIN_ALTITUDE_DEG = 10.0  # low targets are lost in haze, hills and buildings
DEFAULT_MAX_SUN_ALTITUDE_DEG = -6.0  # end of civil twilight: bright planets start to show


@dataclass(frozen=True)
class SiteVisibility:
    """A site that passed the checks, with where to look."""

    site: Site
    distance_km: float
    altitude_deg: float
    azimuth_deg: float
    sun_altitude_deg: float


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

    def visible_sites(
        self,
        body_name: str,
        origin_lat: float,
        origin_lon: float,
        max_distance_km: float,
        when: datetime | None = None,
    ) -> list[SiteVisibility]:
        """Sites within range from which ``body_name`` can be seen at ``when`` (default: now).

        A body counts as visible when it is at least ``min_altitude_deg`` above
        the horizon and, except for the Moon, the Sun is at or below
        ``max_sun_altitude_deg``. Weather is not considered here.
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
        t = self._timescale.from_datetime(when)

        results = []
        for site, distance in self.sites_within(origin_lat, origin_lon, max_distance_km):
            observer = self._earth + wgs84.latlon(
                site.latitude, site.longitude, elevation_m=site.elevation_m
            )
            at_site = observer.at(t)
            alt, az, _ = at_site.observe(body["target"]).apparent().altaz()
            sun_alt, _, _ = at_site.observe(self._sun).apparent().altaz()

            if alt.degrees < self.min_altitude_deg:
                continue
            if needs_darkness and sun_alt.degrees > self.max_sun_altitude_deg:
                continue
            results.append(
                SiteVisibility(
                    site=site,
                    distance_km=round(distance, 1),
                    altitude_deg=round(float(alt.degrees), 1),
                    azimuth_deg=round(float(az.degrees), 1),
                    sun_altitude_deg=round(float(sun_alt.degrees), 1),
                )
            )
        return results
