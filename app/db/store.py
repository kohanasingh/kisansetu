"""Data access layer — every query goes through here, never through
dummy_data.py directly. Backed by the in-memory seeded dataset for the
prototype, with signatures written as if a real DB were behind them so
swapping in a real DB later is a same-signature change, not a rewrite of
calling code.

Note there is deliberately NO msp_for_crop() or schemes_for_profile() —
those facts are not seeded anywhere; the advisory agent draws them from
GPT-4o's own knowledge. See PROJECT_SPEC.md "Sourcing MSP and schemes".
"""

from __future__ import annotations

import re
import uuid
from difflib import SequenceMatcher

from app.db import dummy_data as _data

# Reasonable FPO catchment radius for identity path 3 (nearest-FPO-by-village
# fallback). Beyond this, treat the farmer as outside any FPO's reach —
# identity path 4, general knowledge only.
FPO_CATCHMENT_KM = 60.0

_FUZZY_RATIO = 0.72


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def _fuzzy_contains(haystack: str, needle: str) -> bool:
    """True if `needle` appears in `haystack` verbatim, or a close fuzzy match
    of it does (typos, transliteration variance)."""
    haystack, needle = _normalize(haystack), _normalize(needle)
    if not needle:
        return False
    if needle in haystack:
        return True
    words = haystack.split()
    n_words = needle.split()
    window = len(n_words)
    for i in range(len(words) - window + 1):
        candidate = " ".join(words[i:i + window])
        if SequenceMatcher(None, candidate, needle).ratio() >= _FUZZY_RATIO:
            return True
    return False


# --- FPOs -------------------------------------------------------------

def get_fpo(fpo_id: str) -> dict | None:
    return next((f for f in _data.FPOS if f["id"] == fpo_id), None)


def list_fpos() -> list[dict]:
    return list(_data.FPOS)


def find_fpo_by_name(text: str) -> dict | None:
    """Fuzzy match an FPO name or region mentioned anywhere in free text.
    Used by identity resolution path 2 (farmer names their FPO)."""
    if not text:
        return None
    for fpo in _data.FPOS:
        if _fuzzy_contains(text, fpo["name"]) or _fuzzy_contains(text, fpo["region_name"]):
            return fpo
        # Also try just the place name half of the region ("Nashik" out of
        # "Nashik, Maharashtra") — the common way someone actually says it.
        place = fpo["region_name"].split(",")[0]
        if _fuzzy_contains(text, place):
            return fpo
    return None


def nearest_fpo_to(lat: float, lon: float) -> tuple[dict, float] | None:
    """Nearest FPO to a lat/lon and its distance in km. Used by identity
    resolution path 3 (nearest-FPO-by-village fallback)."""
    from app.services.geo import nearest

    return nearest(lat, lon, _data.FPOS)


def find_village_location(text: str) -> tuple[str, float, float] | None:
    """Fuzzy match a village name mentioned in free text against
    dummy_data.VILLAGES (the prototype's stand-in for geocoding). Returns
    (village_name, lat, lon) for the first match, or None."""
    if not text:
        return None
    for village in _data.VILLAGES:
        if _fuzzy_contains(text, village["name"]):
            return village["name"], village["lat"], village["lon"]
    return None


# --- Farmers ------------------------------------------------------------

def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^\d+]", "", phone or "")


def get_farmer_by_phone(phone: str) -> dict | None:
    target = _normalize_phone(phone)
    if not target:
        return None
    for farmer in _data.FARMERS:
        if _normalize_phone(farmer["phone"]) == target:
            return farmer
        # Tolerate a bare 10-digit number without the country code.
        if target.lstrip("+").endswith(_normalize_phone(farmer["phone"]).lstrip("+")[-10:]):
            return farmer
    return None


def get_farmer(farmer_id: str) -> dict | None:
    return next((f for f in _data.FARMERS if f["id"] == farmer_id), None)


def list_farmers(fpo_id: str | None = None) -> list[dict]:
    if fpo_id is None:
        return list(_data.FARMERS)
    return [f for f in _data.FARMERS if f["fpo_id"] == fpo_id]


def add_farmers(fpo_id: str, rows: list[dict]) -> list[dict]:
    """Merge FPO-approved ingestion rows into the in-memory farmer roster.
    Only called by agents/ingestion.py, and only after FPO staff approve a
    staged batch — nothing here auto-merges. In-memory only, like the rest
    of this prototype's dataset (see CLAUDE.md's "No real FPO data")."""
    fpo = get_fpo(fpo_id)
    added = []
    for row in rows:
        village = row.get("village") or None
        lat, lon = (fpo["lat"], fpo["lon"]) if fpo else (0.0, 0.0)
        match = find_village_location(village) if village else None
        if match:
            _, lat, lon = match
        farmer = {
            "id": f"farmer_ing_{uuid.uuid4().hex[:8]}",
            "name": row.get("name") or "Unnamed farmer",
            "phone": row.get("phone") or "",
            "fpo_id": fpo_id,
            "village": village or (fpo["region_name"] if fpo else "Unknown"),
            "farm_size_acres": row.get("farm_size_acres") or 0,
            "crops": row.get("crops") or [],
            "lat": lat, "lon": lon,
        }
        _data.FARMERS.append(farmer)
        added.append(farmer)
    return added


# --- Crop records ---------------------------------------------------------

def crop_records_for_farmer(farmer_id: str) -> list[dict]:
    return [r for r in _data.CROP_RECORDS if r["farmer_id"] == farmer_id]


# --- Warehouses -----------------------------------------------------------

def list_warehouses(fpo_id: str | None = None) -> list[dict]:
    if fpo_id is None:
        return list(_data.WAREHOUSES)
    return [w for w in _data.WAREHOUSES if w["fpo_id"] == fpo_id]


# --- Alerts -----------------------------------------------------------

def recent_alerts(fpo_id: str | None = None, limit: int = 5) -> list[dict]:
    alerts = _data.ALERTS if fpo_id is None else [a for a in _data.ALERTS if a["fpo_id"] == fpo_id]
    return sorted(alerts, key=lambda a: a["created_at"], reverse=True)[:limit]


def add_alert(alert: dict) -> None:
    """Append a real climate alert (agents/climate.py, evaluated from a
    genuine Open-Meteo forecast) to the in-memory alert feed."""
    _data.ALERTS.append(alert)
