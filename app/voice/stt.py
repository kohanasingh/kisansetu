"""Inbound voice: Whisper transcription. Whisper handles major Indian
languages natively — use a language hint where Whisper's API accepts one,
and fall back to auto-detect otherwise (Whisper 400s on a hint for some
languages, e.g. Punjabi and Bengali, and must never crash intake because of
that). Also returns Whisper's own detected language so the reply path knows
what language to answer in, without hardcoding a Hindi/English default.
"""

from __future__ import annotations

import io
import logging

from app.llm import STT_MODEL, client
from app.services.translate import LANGUAGES

logger = logging.getLogger("kisansetu.stt")

# ISO 639-1 codes Whisper's API accepts as an explicit `language` hint (per
# OpenAI's documented Whisper language list). Codes outside this set are
# still transcribed fine — just via auto-detect, since the API rejects the
# hint itself, not the language.
_HINT_LANGS = {
    "af", "ar", "hy", "az", "be", "bs", "bg", "ca", "zh", "hr", "cs", "da",
    "nl", "en", "et", "fi", "fr", "gl", "de", "el", "he", "hi", "hu", "is",
    "id", "it", "ja", "kn", "kk", "ko", "lv", "lt", "mk", "ms", "mr", "mi",
    "ne", "no", "fa", "pl", "pt", "ro", "ru", "sr", "sk", "sl", "es", "sw",
    "sv", "tl", "ta", "th", "tr", "uk", "ur", "vi", "cy",
}

# Whisper's verbose_json returns a full language NAME ("punjabi"), not an
# ISO code — map it back so the rest of the app can work in codes uniformly.
_NAME_TO_ISO = {name.lower(): code for code, name in LANGUAGES.items()}
_NAME_TO_ISO.setdefault("panjabi", "pa")


def _language_name_to_code(name: str | None) -> str | None:
    if not name:
        return None
    return _NAME_TO_ISO.get(name.strip().lower())


async def transcribe(audio_bytes: bytes, filename: str = "note.ogg",
                      language_hint: str | None = None) -> tuple[str, str | None]:
    """Transcribe a voice note. Returns (transcript, detected_language_code).

    If a language hint is given and Whisper's API supports a hint for it,
    pass it through; if Whisper rejects it, retry with auto-detect so no
    language ever crashes intake. `detected_language_code` is Whisper's own
    best guess (mapped back to ISO 639-1 where recognized), used downstream
    to pick the reply language instead of assuming Hindi or English.
    """

    def _call(with_hint: bool):
        f = io.BytesIO(audio_bytes)
        f.name = filename
        kwargs = {"model": STT_MODEL, "file": f, "response_format": "verbose_json"}
        if with_hint and language_hint:
            kwargs["language"] = language_hint
        return client().audio.transcriptions.create(**kwargs)

    use_hint = bool(language_hint) and language_hint in _HINT_LANGS
    try:
        result = await _call(with_hint=use_hint)
    except Exception:  # noqa: BLE001 — a bad/unsupported hint must not break intake
        if not use_hint:
            raise
        logger.warning("whisper rejected language hint %r; retrying with auto-detect", language_hint)
        result = await _call(with_hint=False)

    text = (result.text or "").strip()
    detected = _language_name_to_code(getattr(result, "language", None)) or (
        language_hint if use_hint else None
    )
    return text, detected
