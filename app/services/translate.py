"""Gemini (gemini-flash-lite-latest) translation, covering Indian languages
where GPT-4o's native output is weak. GPT-4o is instructed to write its
reply directly in the farmer's own language first — this module is a
secondary, optional quality pass on top of that, never the only path a
language depends on.

Calls Gemini through app.llm.chat_text_gemini() — never its own client —
per the provider split in CLAUDE.md (this module and agents/advisory.py
are the only Gemini callers in the codebase).

MUST be fail-open: any error, missing API key, already-native-language
input, or unrecognized language code returns the original text untouched.
A translation failure can never break a reply. See CLAUDE.md hard
constraints.
"""

from __future__ import annotations

import logging
import os

from app.llm import GeminiError, chat_text_gemini, load_prompt

logger = logging.getLogger("kisansetu.translate")

# Languages GPT-4o already handles natively well — never routed through Gemini.
NATIVE = {"hi", "en"}

# ISO 639-1 -> English name, for every language this module can address:
# the languages named in CLAUDE.md's Tier 1 multilingual requirement
# (Punjabi, Bengali, Tamil, Marathi) plus the other major Indian languages
# Whisper transcribes natively. Add more here to expand coverage — nothing
# about the reply path is hardcoded to this specific set.
LANGUAGES = {
    "hi": "Hindi", "en": "English", "pa": "Punjabi", "bn": "Bengali",
    "ta": "Tamil", "mr": "Marathi", "te": "Telugu", "gu": "Gujarati",
    "kn": "Kannada", "ml": "Malayalam", "or": "Odia", "as": "Assamese",
    "ur": "Urdu",
}

LANG_NAMES = {k: v for k, v in LANGUAGES.items() if k not in NATIVE}

_cache: dict[tuple[str, str], str] = {}


def _api_key() -> str | None:
    return os.environ.get("GOOGLE_API_KEY") or None


def supported(target: str | None) -> bool:
    """True only when we should translate: a known non-native language + a key set."""
    return bool(target) and target not in NATIVE and target in LANG_NAMES and _api_key() is not None


async def translate(text: str, target: str) -> str:
    """Translate outbound text into `target`. Returns the original text on
    anything unexpected (no key, native/unknown language, network/API
    error) so callers stay safe — fail-open, never raises."""
    if not text or not text.strip() or not supported(target):
        return text
    cache_key = (target, text)
    if cache_key in _cache:
        return _cache[cache_key]

    system_prompt = load_prompt("translate_quality_pass").format(
        target_language_name=LANG_NAMES[target]
    )
    try:
        out = (await chat_text_gemini(system_prompt, text, what="translate.quality_pass")).strip()
        if out:
            _cache[cache_key] = out
            return out
    except GeminiError:
        logger.exception("gemini translate failed for target=%s; using original text", target)
    return text
