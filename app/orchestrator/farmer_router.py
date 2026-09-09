"""Orchestrator entry point for the farmer chat — used identically by
transports/web_console.py (the /demo mimic) and
transports/whatsapp_cloud.py (real WhatsApp).

Runs orchestrator/identity.py first, then classifies intent + detects
language via GPT-4o JSON-mode (app/prompts/farmer_intent.md), and dispatches
to the matching agent: "storage"/"advisory"/"scheme" go to their
agents/advisory.py counterpart (Gemini, with a GPT-4o fallback baked into
that module — see CLAUDE.md's provider split); "alert" and "general" go to
agents/farmer_query.py, since recent alerts are already part of its facts
dict and agents/climate.py (which will own "alert" once built) isn't wired
in yet.

This is a real conversational path, not a scripted demo sequence — the
same code answers a judge clicking around /demo and a farmer messaging
from their own phone.
"""

from __future__ import annotations

import json
import logging

from app.agentlog import log_event
from app.agents import advisory, farmer_query
from app.llm import LLMError, chat_json, load_prompt
from app.orchestrator import dashboard_state, identity
from app.services import translate as gemini_tr
from app.services.translate import LANGUAGES
from app.transports.base import InboundMessage, OutboundMessage, Transport
from app.voice import stt, tts

_ADVISORY_DISPATCH = {
    "storage": advisory.storage,
    "advisory": advisory.crop_plan,
    "scheme": advisory.schemes,
}

# Intent -> dashboard_state field name, for web/demo.html's FPO Dashboard column.
_DASHBOARD_FIELD = {"storage": "storage", "advisory": "crop_plan", "scheme": "schemes"}

logger = logging.getLogger("kisansetu.farmer_router")

_ASK_IDENTITY_EN = (
    "Welcome to KisanSetu! To give you advice grounded in your own FPO's data, "
    "please tell me your registered mobile number, the name of your FPO, or "
    "the village where you farm."
)


_AUDIO_EXT_BY_MIME = {
    "audio/webm": "note.webm", "audio/ogg": "note.ogg", "audio/mpeg": "note.mp3",
    "audio/mp4": "note.m4a", "audio/wav": "note.wav", "audio/x-wav": "note.wav",
}


async def _incoming_text(msg: InboundMessage) -> tuple[str | None, str | None]:
    """Normalize inbound to text (a photo's caption, if any, for an "image"
    message). Returns (text, whisper_detected_language)."""
    if msg.type in {"text", "button", "image"}:
        return msg.text, None
    if msg.type == "audio" and msg.media:
        filename = _AUDIO_EXT_BY_MIME.get(msg.media_mime or "", "note.ogg")
        text, detected = await stt.transcribe(msg.media, filename=filename)
        log_event("whisper", "voice note transcribed", {"transcript": text, "detected": detected})
        return text, detected
    return None, None


async def _classify(text: str | None, detected_language: str | None) -> dict:
    if not text or not text.strip():
        code = detected_language or "hi"
        return {"intent": "general", "language_code": code, "language_name": LANGUAGES.get(code, "Hindi")}
    try:
        result = await chat_json(load_prompt("farmer_intent"), text, what="farmer_router.intent")
    except LLMError:
        logger.exception("intent classification failed; defaulting to general/hi")
        result = {}
    code = result.get("language_code") or detected_language or "hi"
    return {
        "intent": result.get("intent", "general"),
        "language_code": code,
        "language_name": result.get("language_name") or LANGUAGES.get(code, "Hindi"),
    }


async def _localize(text_en: str, language_code: str, language_name: str) -> str:
    if language_code == "en":
        return text_en
    try:
        user_content = json.dumps(
            {"text": text_en, "target_language_name": language_name}, ensure_ascii=False
        )
        result = await chat_json(
            load_prompt("router_localize"), user_content, what="router.localize",
        )
        translated = (result.get("translation") or "").strip()
        return translated or text_en
    except LLMError:
        logger.exception("localization failed; sending English")
        return text_en


async def _say(transport: Transport, to: str, text: str, language_code: str) -> None:
    final_text = text
    if gemini_tr.supported(language_code):
        final_text = await gemini_tr.translate(text, language_code)

    audio_bytes = None
    try:
        audio_bytes = await tts.speak(final_text, language_code)
    except Exception:  # noqa: BLE001 — text must still go out if TTS fails
        logger.exception("TTS failed; sending text only")

    await transport.send(OutboundMessage(to=to, text=final_text, audio_bytes=audio_bytes))


async def handle_inbound(msg: InboundMessage, transport: Transport) -> None:
    text, detected_language = await _incoming_text(msg)
    classification = await _classify(text, detected_language)
    language_code = classification["language_code"]
    language_name = classification["language_name"]

    log_event("orchestrator", f"inbound {msg.type} from {msg.sender[-6:]}",
              {"text": text, "intent": classification["intent"], "language": language_code})

    identity_ctx = await identity.resolve(msg.sender, text)
    log_event("identity", f"status={identity_ctx['status']}", identity_ctx.get("note"))
    dashboard_state.update(
        msg.sender, fpo=identity_ctx.get("fpo"), identity_status=identity_ctx["status"],
        step_note=identity_ctx.get("note") or "Waiting for enough information to resolve an FPO.",
    )

    intent = classification["intent"]
    if identity_ctx["status"] == "unresolved":
        reply_text = await _localize(_ASK_IDENTITY_EN, language_code, language_name)
    elif msg.type == "image" and msg.media:
        # Photo/soil-report Q&A (CLAUDE.md Tier 3 item 14) is farmer_query's
        # job specifically — read-only Vision reasoning, never advisory.
        reply_text = await farmer_query.answer(
            text or "What can you tell me from this photo?", language_code=language_code,
            language_name=language_name, identity_ctx=identity_ctx,
            image_bytes=msg.media, image_mime=msg.media_mime or "image/jpeg",
        )
        fpo_id = (identity_ctx.get("fpo") or {}).get("id")
        log_event("farmer_query", "answered a photo question", {"fpo_id": fpo_id})
        dashboard_state.update(
            msg.sender, step_note="Farmer Query agent answered a question about an attached photo.",
        )
    elif intent in _ADVISORY_DISPATCH:
        reply_text = await _ADVISORY_DISPATCH[intent](
            text or "", language_code=language_code, language_name=language_name,
            identity_ctx=identity_ctx,
        )
        fpo_id = (identity_ctx.get("fpo") or {}).get("id")
        log_event("advisory", "answered", {"intent": intent, "fpo_id": fpo_id})
        dashboard_state.update(
            msg.sender, **{_DASHBOARD_FIELD[intent]: reply_text},
            step_note=f"Advisory agent answered a {intent} question for this farmer.",
        )
    else:
        reply_text = await farmer_query.answer(
            text or "", language_code=language_code, language_name=language_name,
            identity_ctx=identity_ctx,
        )
        fpo_id = (identity_ctx.get("fpo") or {}).get("id")
        log_event("farmer_query", "answered", {"intent": intent, "fpo_id": fpo_id})
        dashboard_state.update(
            msg.sender, step_note="Farmer Query agent answered from the grounded facts dict.",
        )

    await _say(transport, msg.sender, reply_text, language_code)
