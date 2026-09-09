"""Agent — Advisory. The core recommendation engine, covering three
related outputs in one file (shared FPO context, shared reasoning style):

  - storage: nearest / cheapest / least-full warehouse for a crop and
    quantity. A real deterministic lookup over seeded warehouse data — the
    one part of this agent with structured data behind it.
  - crop planning: what to grow next season, reasoned over MSP, a demand
    signal, and weather/soil fit.
  - schemes: which real government schemes fit a farmer or FPO profile.

MSP figures and scheme names are deliberately NOT seeded anywhere in this
repo — they are real public information already in GPT-4o's knowledge, and
fabricating a table would make answers less credible, not more. The prompts
(app/prompts/advisory_crop.md, advisory_schemes.md) instruct the model to
state real figures/names from its own knowledge with an "indicative, may be
outdated" disclaimer. See PROJECT_SPEC.md "Sourcing MSP and schemes".

Drives the live dashboard column on web/demo.html and the advisory panel on
web/fpo.html.

Provider (CLAUDE.md hard constraint — the one narrow exception to
"OpenAI for everything"): every call in this file goes through
llm.chat_json_gemini() first. On a GeminiError (retries already exhausted
inside llm.py), it's caught here and retried via llm.chat_json() (GPT-4o)
instead of surfacing an error to the FPO. Every fallback is logged through
agentlog.log_event("advisory", ...) so it's visible on the demo's
agent-activity feed, never silent. No other agent in this codebase uses
Gemini except services/translate.py.
"""

from __future__ import annotations

import json

from app.agentlog import log_event
from app.db import store
from app.llm import GeminiError, chat_json, chat_json_gemini, load_prompt
from app.services.geo import haversine_km


async def _reason(prompt_name: str, payload: dict, *, what: str) -> dict:
    system_prompt = load_prompt(prompt_name)
    user_content = json.dumps(payload, ensure_ascii=False)
    try:
        return await chat_json_gemini(system_prompt, user_content, what=f"advisory.{what}")
    except GeminiError as e:
        log_event("advisory", f"Gemini failed for {what}; falling back to GPT-4o", {"error": str(e)})
        return await chat_json(system_prompt, user_content, what=f"advisory.{what}.fallback")


def _farmer_brief(farmer: dict | None) -> dict | None:
    if not farmer:
        return None
    return {
        "name": farmer["name"], "village": farmer["village"],
        "farm_size_acres": farmer["farm_size_acres"], "crops": farmer["crops"],
    }


_NO_ANSWER = "I'm sorry, I couldn't work out an answer to that."


def storage_candidates(fpo_id: str, farmer: dict | None) -> list[dict]:
    """Real deterministic lookup — every number here comes straight from
    db/store.py. The LLM only picks a tradeoff to explain, never a number."""
    candidates = []
    for w in store.list_warehouses(fpo_id):
        distance_km = None
        if farmer and farmer.get("lat") is not None and farmer.get("lon") is not None:
            distance_km = round(haversine_km(farmer["lat"], farmer["lon"], w["lat"], w["lon"]), 1)
        candidates.append({
            "name": w["name"],
            "free_quintal": w["capacity_quintal"] - w["occupied_quintal"],
            "capacity_quintal": w["capacity_quintal"],
            "cost_per_quintal": w["cost_per_quintal"],
            "distance_km": distance_km,
        })
    candidates.sort(key=lambda c: c["distance_km"] if c["distance_km"] is not None else float("inf"))
    return candidates


async def storage(question: str, *, language_code: str, language_name: str,
                   identity_ctx: dict) -> str:
    farmer = identity_ctx.get("farmer")
    fpo = identity_ctx.get("fpo")
    candidates = storage_candidates(fpo["id"], farmer) if fpo else []

    payload = {
        "question": question, "language_code": language_code, "language_name": language_name,
        "farmer": _farmer_brief(farmer), "candidates": candidates,
        "personalized": identity_ctx.get("personalized", False),
        "personalization_note": identity_ctx.get("note", ""),
    }
    result = await _reason("advisory_storage", payload, what="storage")
    return result.get("reply") or _NO_ANSWER


async def crop_plan(question: str, *, language_code: str, language_name: str,
                     identity_ctx: dict) -> str:
    farmer = identity_ctx.get("farmer")
    fpo = identity_ctx.get("fpo")

    payload = {
        "question": question, "language_code": language_code, "language_name": language_name,
        "farmer": _farmer_brief(farmer),
        "region": fpo["region_name"] if fpo else None,
        "crop_records": store.crop_records_for_farmer(farmer["id"]) if farmer else [],
        "personalized": identity_ctx.get("personalized", False),
        "personalization_note": identity_ctx.get("note", ""),
    }
    result = await _reason("advisory_crop", payload, what="crop_plan")
    return result.get("reply") or _NO_ANSWER


async def schemes(question: str, *, language_code: str, language_name: str,
                   identity_ctx: dict) -> str:
    farmer = identity_ctx.get("farmer")
    fpo = identity_ctx.get("fpo")

    payload = {
        "question": question, "language_code": language_code, "language_name": language_name,
        "farmer": _farmer_brief(farmer),
        "region": fpo["region_name"] if fpo else None,
        "personalized": identity_ctx.get("personalized", False),
        "personalization_note": identity_ctx.get("note", ""),
    }
    result = await _reason("advisory_schemes", payload, what="schemes")
    return result.get("reply") or _NO_ANSWER
