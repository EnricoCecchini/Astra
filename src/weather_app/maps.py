"""Map of the user's location and the suggested observing sites."""

from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, log2, radians, sin

import plotly.graph_objects as go

from .utils import EARTH_RADIUS_KM

# Marker colour per visibility status (distinguishable with common colour blindness).
STATUS_COLORS = {
    "Visible now": "#1a9850",
    "Visible later": "#f59e0b",
    "Not visible soon": "#9ca3af",
}
USER_COLOR = "#2563eb"
MAP_HEIGHT_PX = 450


@dataclass(frozen=True)
class SiteMarker:
    name: str
    latitude: float
    longitude: float
    status: str  # a key of STATUS_COLORS
    hover: str  # HTML shown when hovering the marker


def circle_points(lat: float, lon: float, radius_km: float, n: int = 90):
    """Points of a circle of ``radius_km`` around (lat, lon), for drawing on a map."""
    phi1, lambda1 = radians(lat), radians(lon)
    d = radius_km / EARTH_RADIUS_KM
    lats, lons = [], []
    for i in range(n + 1):
        bearing = radians(360 * i / n)
        phi2 = asin(sin(phi1) * cos(d) + cos(phi1) * sin(d) * cos(bearing))
        lambda2 = lambda1 + atan2(
            sin(bearing) * sin(d) * cos(phi1), cos(d) - sin(phi1) * sin(phi2)
        )
        lats.append(degrees(phi2))
        lons.append(degrees(lambda2))
    return lats, lons


def zoom_for_radius(lat: float, radius_km: float, height_px: int = MAP_HEIGHT_PX) -> float:
    """Web-map zoom level at which a circle of ``radius_km`` fits the map height."""
    metres_per_px_at_zoom0 = 156_543.03 * cos(radians(lat))
    target_metres_per_px = 2.4 * radius_km * 1000 / height_px  # diameter plus margin
    return log2(metres_per_px_at_zoom0 / target_metres_per_px)


def sites_map(
    user_lat: float, user_lon: float, radius_km: float, markers: list[SiteMarker]
) -> go.Figure:
    """Plotly map: travel radius, the user's position and one marker per site."""
    fig = go.Figure()

    circle_lats, circle_lons = circle_points(user_lat, user_lon, radius_km)
    fig.add_trace(
        go.Scattermap(
            lat=circle_lats,
            lon=circle_lons,
            mode="lines",
            line={"color": USER_COLOR, "width": 1.5},
            name=f"Travel radius ({radius_km} km)",
            hoverinfo="skip",
        )
    )

    for status, color in STATUS_COLORS.items():
        group = [m for m in markers if m.status == status]
        if not group:
            continue
        fig.add_trace(
            go.Scattermap(
                lat=[m.latitude for m in group],
                lon=[m.longitude for m in group],
                mode="markers+text",
                marker={"size": 16, "color": color},
                text=[m.name for m in group],
                textposition="top center",
                hovertext=[m.hover for m in group],
                hoverinfo="text",
                name=status,
                legendgroup="sites",
                legendgrouptitle={"text": "Suggested sites"},
            )
        )

    fig.add_trace(
        go.Scattermap(
            lat=[user_lat],
            lon=[user_lon],
            mode="markers+text",
            marker={"size": 14, "color": USER_COLOR},
            text=["You are here"],
            textposition="bottom center",
            textfont={"color": USER_COLOR},
            hovertext=["Your current location"],
            hoverinfo="text",
            name="Your current location",
        )
    )

    fig.update_layout(
        map={
            "style": "carto-positron",
            "center": {"lat": user_lat, "lon": user_lon},
            "zoom": zoom_for_radius(user_lat, radius_km),
        },
        height=MAP_HEIGHT_PX,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        legend={"orientation": "h", "yanchor": "bottom", "y": 0.01, "x": 0.01,
                "bgcolor": "rgba(255,255,255,0.85)"},
    )
    return fig
