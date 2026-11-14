"""Small, dependency-free helper functions shared across modules."""

from math import asin, cos, radians, sin, sqrt
from urllib.parse import urlencode

EARTH_RADIUS_KM = 6371.0088  # mean Earth radius (IUGG)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two points given in decimal degrees.

    Treats the Earth as a sphere, so results can be off by up to ~0.5%
    compared with the true (ellipsoidal) distance — fine for ranking sites.
    """
    for lat in (lat1, lat2):
        if not -90 <= lat <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
    for lon in (lon1, lon2):
        if not -180 <= lon <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    # min() guards against a > 1 from floating-point rounding on antipodal points.
    return 2 * EARTH_RADIUS_KM * asin(min(1.0, sqrt(a)))


COMPASS_POINTS = [
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
]


def compass_point(azimuth_deg: float) -> str:
    """16-point compass direction for an azimuth (0° = north, 90° = east)."""
    return COMPASS_POINTS[round(azimuth_deg % 360 / 22.5) % 16]


def google_maps_directions_url(
    origin_lat: float, origin_lon: float, dest_lat: float, dest_lon: float
) -> str:
    """Google Maps link with driving directions from the origin to the destination."""
    query = urlencode(
        {
            "api": 1,
            "origin": f"{origin_lat},{origin_lon}",
            "destination": f"{dest_lat},{dest_lon}",
            "travelmode": "driving",
        }
    )
    return f"https://www.google.com/maps/dir/?{query}"
