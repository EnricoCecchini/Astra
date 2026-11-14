"""Celestial bodies available from Skyfield."""

from __future__ import annotations

from pathlib import Path

from skyfield.api import Loader, load_constellation_names
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
    ``target``: the Skyfield vector for solar-system bodies, or the IAU
    three-letter abbreviation for constellations (they are areas of sky, not points).
    """
    ephemeris = ephemeris or load_ephemeris()
    bodies: dict[str, dict] = {}

    for name in PLANET_NAMES:
        bodies[name] = {"kind": "planet", "target": _ephemeris_target(ephemeris, name)}
    for name in EXTRA_BODIES:
        bodies[name] = {"kind": "moon", "target": _ephemeris_target(ephemeris, name)}

    for abbreviation, name in sorted(load_constellation_names(), key=lambda pair: pair[1]):
        bodies[name] = {"kind": "constellation", "target": abbreviation}

    return bodies
