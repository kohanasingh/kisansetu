"""Farmer identity resolution — runs before intent classification on every
inbound farmer message. Four paths, in order:

  1. Registered phone recognized -> phone->FPO lookup -> full personalized
     context. Checked on every message (real WhatsApp always sends the same
     phone number, so this never needs caching).
  2. Not registered, farmer names their FPO -> fuzzy/substring match against
     the FPO table -> same personalized context.
  3. Not registered, no FPO named, farmer gives a village or location ->
     nearest FPO via services/geo.py haversine distance, within
     db/store.FPO_CATCHMENT_KM -> borrow that FPO's context.
  4. No FPO within that radius -> no personalization, general knowledge
     only, and the assistant says so plainly rather than pretending to have
     local data.

If none of the four can be determined yet (first message, no clues in the
text), status is "unresolved" — farmer_router.py short-circuits to asking
for a registered number, FPO name, or village, exactly as PROJECT_SPEC
describes for the first turn on real WhatsApp.

Paths 2-4 are cached per sender for the rest of the conversation once
resolved, so a farmer doesn't have to repeat their FPO/village every
message. Path 1 is never cached — trusting the phone number itself is
strictly better than trusting a cache of it.

The returned context dict IS the RAG substitute for this prototype — see
PROJECT_SPEC.md "Why no RAG in this prototype".
"""

from __future__ import annotations

from app.db import store

_cache: dict[str, dict] = {}


def _context(status: str, *, farmer: dict | None, fpo: dict | None, note: str,
             distance_km: float | None = None) -> dict:
    return {
        "status": status,
        "personalized": status in {"registered", "fpo_named", "village_nearest"},
        "farmer": farmer,
        "fpo": fpo,
        "distance_km": distance_km,
        "note": note,
    }


async def resolve(sender: str, text: str | None) -> dict:
    # Path 1 — registered phone. Always checked fresh; never cached.
    farmer = store.get_farmer_by_phone(sender)
    if farmer:
        fpo = store.get_fpo(farmer["fpo_id"])
        return _context(
            "registered", farmer=farmer, fpo=fpo,
            note=f"Resolved by registered phone number to {fpo['name']}.",
        )

    cached = _cache.get(sender)
    if cached is not None:
        return cached

    # Path 2 — farmer names their FPO.
    fpo = store.find_fpo_by_name(text or "")
    if fpo:
        ctx = _context(
            "fpo_named", farmer=None, fpo=fpo,
            note=f"No registered number given; resolved by FPO name to {fpo['name']}.",
        )
        _cache[sender] = ctx
        return ctx

    # Path 3 / 4 — farmer gives a village or location.
    village_match = store.find_village_location(text or "")
    if village_match:
        village, lat, lon = village_match
        nearest = store.nearest_fpo_to(lat, lon)
        if nearest and nearest[1] <= store.FPO_CATCHMENT_KM:
            near_fpo, dist_km = nearest
            ctx = _context(
                "village_nearest", farmer=None, fpo=near_fpo, distance_km=round(dist_km, 1),
                note=(f"No registered number or FPO given; resolved nearest FPO to "
                      f"{village} ({near_fpo['name']}, {dist_km:.0f} km away)."),
            )
        else:
            dist_km = nearest[1] if nearest else None
            ctx = _context(
                "no_fpo_nearby", farmer=None, fpo=None,
                distance_km=round(dist_km, 1) if dist_km is not None else None,
                note=(f"{village} is outside any FPO's catchment area "
                      f"({store.FPO_CATCHMENT_KM:.0f} km) — no local data available, "
                      "answering from general knowledge only."),
            )
        _cache[sender] = ctx
        return ctx

    # Nothing recognized yet — not a terminal state, so not cached; the
    # farmer may say more in their next message.
    return _context(
        "unresolved", farmer=None, fpo=None,
        note="No registered phone, FPO name, or village recognized yet.",
    )


def reset(sender: str | None = None) -> None:
    """Clear cached resolution — used by the demo reset control."""
    if sender is None:
        _cache.clear()
    else:
        _cache.pop(sender, None)
