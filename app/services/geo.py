"""Haversine distance between two lat/lon points.

Used by orchestrator/identity.py (path 3: nearest-FPO fallback when a farmer
has no registered number and names no FPO) and by agents/advisory.py
(nearest warehouse for a storage recommendation).
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearest(lat: float, lon: float, candidates: list[dict], *, lat_key: str = "lat",
            lon_key: str = "lon") -> tuple[dict, float] | None:
    """Nearest candidate dict (by lat/lon fields) and its distance in km. None if
    candidates is empty."""
    best = None
    best_km = None
    for c in candidates:
        d = haversine_km(lat, lon, c[lat_key], c[lon_key])
        if best_km is None or d < best_km:
            best, best_km = c, d
    return (best, best_km) if best is not None else None
