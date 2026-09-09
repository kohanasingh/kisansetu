"""Agent — Farmer Q&A. The grounded free-form answer path behind the farmer
chat, on both transports.

Assembles a facts dict (the farmer's own record + their resolved FPO's
warehouses + recent regional alerts) and lets GPT-4o answer in the farmer's
own language, grounded ONLY in what that dict contains. If a fact isn't in
the dict, the model says it doesn't know rather than guessing — this
anti-hallucination discipline is a hard constraint (CLAUDE.md).

Multilingual is Tier 1: the reply path must not be hardcoded to
Hindi/English — see app/prompts/farmer_general_answer.md.

Photo/soil-report Q&A (CLAUDE.md Tier 3 item 14): a farmer can attach a
crop or soil-report photo to their question. GPT-4o Vision looks at it
read-only — describing/reasoning about what's in the image never writes
data, it's purely part of forming the answer.
"""

from __future__ import annotations

import json

from app.db import store
from app.llm import NO_ANSWER_FALLBACK, chat_json, image_content, load_prompt


def _build_facts(identity_ctx: dict) -> dict:
    fpo = identity_ctx.get("fpo")
    farmer = identity_ctx.get("farmer")
    facts: dict = {}

    if farmer:
        facts["farmer"] = {
            "name": farmer["name"],
            "village": farmer["village"],
            "farm_size_acres": farmer["farm_size_acres"],
            "crops": farmer["crops"],
        }
        facts["crop_records"] = store.crop_records_for_farmer(farmer["id"])

    if fpo:
        facts["fpo"] = {"name": fpo["name"], "region": fpo["region_name"]}
        facts["warehouses"] = store.list_warehouses(fpo["id"])
        facts["recent_alerts"] = store.recent_alerts(fpo["id"])

    return facts


async def answer(question: str, *, language_code: str, language_name: str,
                  identity_ctx: dict, image_bytes: bytes | None = None,
                  image_mime: str = "image/jpeg") -> str:
    facts = _build_facts(identity_ctx)
    text_content = json.dumps({
        "question": question,
        "language_code": language_code,
        "language_name": language_name,
        "facts": facts,
        "personalized": identity_ctx.get("personalized", False),
        "personalization_note": identity_ctx.get("note", ""),
        "has_photo": image_bytes is not None,
    }, ensure_ascii=False)

    user_content = (
        [{"type": "text", "text": text_content}, image_content(image_bytes, mime=image_mime)]
        if image_bytes else text_content
    )

    result = await chat_json(
        load_prompt("farmer_general_answer"), user_content, what="farmer_query.answer",
    )
    return result.get("reply") or NO_ANSWER_FALLBACK
