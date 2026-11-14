"""Celestial bodies available from Skyfield."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from skyfield.api import (
    Loader,
    Star,
    load_constellation_map,
    load_constellation_names,
    position_of_radec,
)
from skyfield.jpllib import SpiceKernel
from skyfield.vectorlib import VectorFunction

EPHEMERIS_FILE = "de421.bsp"  # JPL ephemeris covering 1900-2050 (~17 MB, downloaded once)
EPHEMERIS_DIR = Path(__file__).resolve().parents[2] / "data" / "skyfield"

# The ephemeris lists bodies by NAIF code and does not say which ones are planets,
# so the planet list is fixed here. The Moon is included because it is an
# observing target in the project plan.
PLANET_NAMES = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
EXTRA_BODIES = ["Moon"]


def load_ephemeris(directory: Path = EPHEMERIS_DIR) -> SpiceKernel:
    """Load the JPL ephemeris, downloading it into ``directory`` on first use."""
    directory.mkdir(parents=True, exist_ok=True)
    return Loader(str(directory), verbose=False)(EPHEMERIS_FILE)


def _ephemeris_target(ephemeris: SpiceKernel, name: str) -> VectorFunction:
    """Return the body itself if the ephemeris has it, otherwise its barycenter.

    DE421 has Mercury, Venus, Mars and the Moon as bodies, but the outer planets
    only as system barycenters, which are accurate enough for naked-eye pointing.
    """
    known = {alias for aliases in ephemeris.names().values() for alias in aliases}
    key = name.upper()
    if key not in known:
        key = f"{key} BARYCENTER"
    return ephemeris[key]


def load_celestial_bodies(ephemeris: SpiceKernel | None = None) -> dict[str, dict]:
    """Build the CELESTIAL_BODY dictionary: display name -> details.

    Each value has a ``kind`` ("planet", "moon" or "constellation") and a
    ``target`` that Skyfield can observe: the ephemeris vector for solar-system
    bodies, or a fixed ``Star`` at the constellation's approximate centre
    (constellations are areas of sky, not points). Constellations also carry
    their IAU three-letter ``abbreviation``.
    """
    ephemeris = ephemeris or load_ephemeris()
    bodies: dict[str, dict] = {}

    for name in PLANET_NAMES:
        bodies[name] = {"kind": "planet", "target": _ephemeris_target(ephemeris, name)}
    for name in EXTRA_BODIES:
        bodies[name] = {"kind": "moon", "target": _ephemeris_target(ephemeris, name)}

    centers = constellation_centers()
    for abbreviation, name in sorted(load_constellation_names(), key=lambda pair: pair[1]):
        ra_hours, dec_deg = centers[abbreviation]
        bodies[name] = {
            "kind": "constellation",
            "abbreviation": abbreviation,
            "target": Star(ra_hours=ra_hours, dec_degrees=dec_deg),
        }

    return bodies


def constellation_centers(step_deg: float = 1.0) -> dict[str, tuple[float, float]]:
    """Approximate centre of each constellation as (RA in hours, Dec in degrees).

    Skyfield only provides a point -> constellation lookup, so the sky is sampled
    on a regular RA/Dec grid and the unit vectors of each constellation's points
    are averaged, weighted by cos(Dec) so every sample stands for an equal area.
    """
    ra_deg, dec_deg = np.meshgrid(
        np.arange(step_deg / 2, 360, step_deg), np.arange(-90 + step_deg / 2, 90, step_deg)
    )
    ra_deg, dec_deg = ra_deg.ravel(), dec_deg.ravel()
    names = load_constellation_map()(position_of_radec(ra_deg / 15, dec_deg))

    ra, dec = np.radians(ra_deg), np.radians(dec_deg)
    weight = np.cos(dec)
    xyz = np.column_stack((np.cos(dec) * np.cos(ra), np.cos(dec) * np.sin(ra), np.sin(dec)))

    centers = {}
    for abbreviation in np.unique(names):
        mask = names == abbreviation
        x, y, z = (xyz[mask] * weight[mask, None]).sum(axis=0)
        centers[str(abbreviation)] = (
            float(np.degrees(np.arctan2(y, x)) % 360 / 15),
            float(np.degrees(np.arctan2(z, np.hypot(x, y)))),
        )
    return centers
