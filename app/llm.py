"""Shared LLM clients — the single place every model call goes through,
for both providers.

Provides chat_json() for structured JSON-mode output, chat_text() for
free-form replies, image_content() for Vision calls, load_prompt() to load
versioned prompt files from app/prompts/ (never inline prompt strings in
agent code), and a shared retry/backoff wrapper so every agent inherits the
same resilience — all on GPT-4o.

Also provides chat_json_gemini() / chat_text_gemini(): same signature shape
as their GPT-4o counterparts, backed by Gemini (gemini-flash-lite-latest)
with the same retry/backoff pattern. Per CLAUDE.md's provider split, THIS
GEMINI PATH IS USED BY agents/advisory.py AND services/translate.py ONLY —
every other agent (intent classification, farmer_query, Whisper, TTS,
Vision) stays on GPT-4o. Callers that need to survive a Gemini outage (i.e.
advisory.py) catch GeminiError and retry via chat_json()/chat_text().

Hard constraint: agents never instantiate or call the OpenAI or Gemini
client directly — always through here. See CLAUDE.md.
"""

from __future__ import annotations

import base64
import functools
import json
import logging
import os
from pathlib import Path

import httpx
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

from app.retry import with_retry

logger = logging.getLogger("kisansetu.llm")

TEXT_MODEL = "gpt-4o"
VISION_MODEL = "gpt-4o"
STT_MODEL = "whisper-1"
TTS_MODEL = "gpt-4o-mini-tts"
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Shared fallback text for a grounded-answer agent that got an empty reply
# from the model — agents/advisory.py, agents/farmer_query.py, and
# orchestrator/fpo_router.py all use this instead of each defining their own.
NO_ANSWER_FALLBACK = "I'm sorry, I couldn't work out an answer to that."

_client: AsyncOpenAI | None = None


class LLMError(Exception):
    """Raised after OpenAI retries are exhausted."""


class GeminiError(Exception):
    """Raised after Gemini retries are exhausted. advisory.py catches this
    to fall back to GPT-4o; translate.py catches this as part of its own
    fail-open (returns the original text)."""


class MissingAPIKeyError(RuntimeError):
    """Raised at startup when a required key is absent — fails loudly and
    early rather than surfacing as a confusing error mid-conversation."""


def require_openai_key() -> None:
    """Call once at app startup. OPENAI_API_KEY is load-bearing for nearly
    every Tier 1 feature (GPT-4o, Whisper, TTS) — refuse to start without it
    rather than fail unpredictably on the first request."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise MissingAPIKeyError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add a "
            "real key before starting the server."
        )


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI()
    return _client


@functools.lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load a versioned prompt file from app/prompts/ (never inline strings).
    Cached — prompt files are static for the life of the process, and this
    is called on every single agent call, so an uncached disk read here
    would block the event loop on every concurrent request."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def image_content(image_bytes: bytes, mime: str = "image/jpeg", detail: str = "high") -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": detail}}


async def _with_retry(coro_factory, what: str):
    return await with_retry(
        coro_factory, what=what,
        exceptions=(APIError, APITimeoutError, RateLimitError, json.JSONDecodeError),
        error_cls=LLMError,
    )


async def chat_json(system_prompt: str, user_content, *, model: str = TEXT_MODEL,
                     what: str = "llm-call", temperature: float | None = None) -> dict:
    """One chat completion returning a parsed JSON object."""

    async def call():
        kwargs = {"temperature": temperature} if temperature is not None else {}
        response = await client().chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            **kwargs,
        )
        return json.loads(response.choices[0].message.content)

    return await _with_retry(call, what)


async def chat_text(system_prompt: str, user_content, *, model: str = TEXT_MODEL,
                     what: str = "llm-call") -> str:
    async def call():
        response = await client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content

    return await _with_retry(call, what)


def _gemini_api_key() -> str | None:
    return os.environ.get("GOOGLE_API_KEY") or None


async def _gemini_generate(system_prompt: str, user_content, *, model: str, want_json: bool) -> str:
    key = _gemini_api_key()
    if not key:
        raise GeminiError("GOOGLE_API_KEY is not set")

    body: dict = {
        "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_content}"}]}],
        "generationConfig": {"temperature": 0.3},
    }
    if want_json:
        body["generationConfig"]["response_mime_type"] = "application/json"

    url = f"{GEMINI_URL.format(model=model)}?key={key}"
    async with httpx.AsyncClient(timeout=20) as http:
        response = await http.post(url, json=body)
        response.raise_for_status()
        data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise GeminiError(f"unexpected Gemini response shape: {data}") from e


async def _with_retry_gemini(coro_factory, what: str):
    return await with_retry(
        coro_factory, what=f"{what} (gemini)",
        exceptions=(httpx.HTTPError, GeminiError, json.JSONDecodeError),
        error_cls=GeminiError,
    )


async def chat_json_gemini(system_prompt: str, user_content, *, model: str = GEMINI_MODEL,
                            what: str = "llm-call") -> dict:
    """Gemini counterpart to chat_json() — identical signature shape.
    Restricted to agents/advisory.py and services/translate.py (see module
    docstring). Raises GeminiError after retries are exhausted."""

    async def call():
        text = await _gemini_generate(system_prompt, user_content, model=model, want_json=True)
        return json.loads(text)

    return await _with_retry_gemini(call, what)


async def chat_text_gemini(system_prompt: str, user_content, *, model: str = GEMINI_MODEL,
                            what: str = "llm-call") -> str:
    """Gemini counterpart to chat_text() — identical signature shape.
    Same scope restriction as chat_json_gemini()."""

    async def call():
        return await _gemini_generate(system_prompt, user_content, model=model, want_json=False)

    return await _with_retry_gemini(call, what)
