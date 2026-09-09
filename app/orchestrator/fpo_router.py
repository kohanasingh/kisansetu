"""Orchestrator entry point for the FPO staff chatbot on web/fpo.html.

Simpler than farmer_router.py — no identity resolution step, since the
dashboard is scoped to a single FPO (there is no login in this prototype;
see CLAUDE.md "What NOT to build"). Classifies intent via GPT-4o JSON-mode
(app/prompts/fpo_chat_intent.md) and dispatches:
  - "advisory" -> the matching agents/advisory.py function (Gemini, with
    the GPT-4o fallback baked into that module).
  - "climate" / "ingestion-status" / "general" -> a grounded answer over
    this FPO's own facts (roster, warehouses, alerts, pending uploads),
    always GPT-4o — these are plain lookups, not reasoning that benefits
    from a second provider.
"""

from __future__ import annotations

import json
import logging

from app.agentlog import log_event
from app.agents import advisory, ingestion
from app.db import store
from app.llm import NO_ANSWER_FALLBACK, LLMError, chat_json, load_prompt

logger = logging.getLogger("kisansetu.fpo_router")

_STORAGE_WORDS = {"storage", "warehouse", "godown", "space", "quintal"}
_SCHEME_WORDS = {"scheme", "subsidy", "pm-kisan", "pmfby", "kcc", "loan", "insurance", "government"}


async def _classify(text: str) -> str:
    try:
        result = await chat_json(load_prompt("fpo_chat_intent"), text, what="fpo_router.intent")
        return result.get("intent", "general")
    except LLMError:
        logger.exception("fpo intent classification failed; defaulting to general")
        return "general"


def _advisory_subtype(text: str) -> str:
    """Which agents/advisory.py function best fits an 'advisory'-tagged
    question — a light keyword heuristic (not a second LLM call), since
    fpo_chat_intent.md deliberately keeps 'advisory' as one merged
    category. Defaults to crop planning, the broadest of the three."""
    lower = text.lower()
    if any(w in lower for w in _STORAGE_WORDS):
        return "storage"
    if any(w in lower for w in _SCHEME_WORDS):
        return "scheme"
    return "advisory"


def _fpo_facts(fpo: dict) -> dict:
    fpo_id = fpo["id"]
    farmers = store.list_farmers(fpo_id)
    pending = [b for b in ingestion.list_batches(fpo_id) if b["status"] == "pending"]
    return {
        "fpo": fpo,
        "farmer_count": len(farmers),
        "farmers": [{"name": f["name"], "village": f["village"], "crops": f["crops"]} for f in farmers],
        "warehouses": store.list_warehouses(fpo_id),
        "recent_alerts": store.recent_alerts(fpo_id, limit=5),
        "pending_uploads": [{"source": b["source"], "row_count": b["row_count"]} for b in pending],
    }


async def answer(fpo_id: str, question: str) -> str:
    fpo = store.get_fpo(fpo_id)
    if fpo is None:
        return "I don't recognize that FPO."

    intent = await _classify(question)
    log_event("fpo_router", f"intent={intent}", {"fpo_id": fpo_id})

    if intent == "advisory":
        identity_ctx = {"fpo": fpo, "farmer": None, "personalized": True, "note": "FPO staff question."}
        kwargs = dict(language_code="en", language_name="English", identity_ctx=identity_ctx)
        subtype = _advisory_subtype(question)
        fn = {"storage": advisory.storage, "scheme": advisory.schemes}.get(subtype, advisory.crop_plan)
        return await fn(question, **kwargs)

    facts = _fpo_facts(fpo)
    user_content = json.dumps({"question": question, "facts": facts}, ensure_ascii=False)
    try:
        result = await chat_json(load_prompt("fpo_general_answer"), user_content, what="fpo_router.answer")
        return result.get("reply") or NO_ANSWER_FALLBACK
    except LLMError:
        logger.exception("fpo_router general answer failed")
        return "I'm having trouble answering right now — please try again."
