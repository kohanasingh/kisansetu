"""Outbound voice: gpt-4o-mini-tts. Renders spoken replies as browser-
playable audio for the demo console, and as WhatsApp voice notes for the
real transport.

Multilingual is Tier 1 — the instructions given to the model describe tone
only and explicitly tell it to keep speaking in whatever language the input
text is already written in, so nothing here silently falls back to Hindi or
English for a language it doesn't have a bespoke entry for.
"""

from __future__ import annotations

from app.llm import TTS_MODEL, client
from app.services.translate import LANGUAGES

VOICE = "alloy"

_BASE_INSTRUCTIONS = (
    "Speak in a warm, clear, unhurried voice, like a patient younger relative "
    "explaining something helpful to an elder in a village. Read the input text "
    "in its own language and script exactly as written — do not translate it or "
    "switch to a different language."
)


def _instructions(language_code: str | None) -> str:
    name = LANGUAGES.get(language_code or "") if language_code else None
    if name:
        return f"{_BASE_INSTRUCTIONS} The input text is in {name}."
    return _BASE_INSTRUCTIONS


async def speak(text: str, language_code: str | None = None) -> bytes:
    """Render text to OGG/Opus bytes (WhatsApp's native voice-note format)."""
    response = await client().audio.speech.create(
        model=TTS_MODEL,
        voice=VOICE,
        input=text,
        response_format="opus",
        instructions=_instructions(language_code),
    )
    return response.content
