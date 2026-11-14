"""Data classes shared across modules."""

from __future__ import annotations

from dataclasses import dataclass

from .utils import haversine_km


@dataclass(frozen=True, kw_only=True)
class Site:
    """One observing site, as listed in ``data/sites.csv``."""

    site_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float = 0.0
    owm_location_id: int | None = None
    sky_brightness: float | None = None  # optional light-pollution value

    def __post_init__(self) -> None:
        if not self.site_id:
            raise ValueError("site_id must not be empty")
        if not -90 <= self.latitude <= 90:
            raise ValueError(f"{self.site_id}: latitude {self.latitude} is outside -90..90")
        if not -180 <= self.longitude <= 180:
            raise ValueError(f"{self.site_id}: longitude {self.longitude} is outside -180..180")

    def distance_km(self, lat: float, lon: float) -> float:
        """Straight-line (great-circle) distance from this site to a point."""
        return haversine_km(self.latitude, self.longitude, lat, lon)

    def __repr__(self) -> str:
        return f"Site({self.site_id!r}, {self.latitude:.4f}, {self.longitude:.4f})"
