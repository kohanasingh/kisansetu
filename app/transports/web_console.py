"""WhatsApp-styled demo console transport — a real client (in-memory
per-session outbox, polled by the frontend), driving the identical
orchestrator path as transports/whatsapp_cloud.py.

Its job is to let a tester use exactly what a farmer would see on their own
WhatsApp, without a live Meta phone number. This is a REAL live agent path,
not a scripted playback — a judge can type or speak and get a genuine
grounded answer, and all four identity-resolution paths work if tried.
(The demo control buttons on web/demo.html are separate: they only fire
external events like a climate alert or an FPO batch upload.)

Also used, more simply, for the FPO staff chatbot on web/fpo.html.

There is no external object storage in this prototype (no DB at all — see
CLAUDE.md), so outbound TTS audio is held in an in-memory byte store here
and served back by app/main.py at the URL store_audio() returns.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from app.transports.base import OutboundMessage, Transport

_outbox: dict[str, list[dict]] = defaultdict(list)
_audio: dict[str, bytes] = {}


class WebConsoleTransport(Transport):
    name = "web_console"

    async def send(self, message: OutboundMessage) -> None:
        audio_url = store_audio(message.audio_bytes) if message.audio_bytes else None
        _outbox[message.to].append({
            "ts": time.time(),
            "text": message.text,
            "audio_url": audio_url,
            "image_url": message.image_url,
            "buttons": [{"id": b.id, "label": b.label} for b in message.buttons],
            "meta": message.meta,
        })


def poll(session: str, since: int = 0) -> dict:
    messages = _outbox.get(session, [])
    return {"messages": messages[since:], "next": len(messages)}


def reset(session: str | None = None) -> None:
    if session is None:
        _outbox.clear()
        _audio.clear()
    else:
        _outbox.pop(session, None)


def store_audio(data: bytes) -> str:
    """Hold TTS bytes in memory, return the URL app/main.py will serve them at."""
    audio_id = uuid.uuid4().hex
    _audio[audio_id] = data
    return f"/api/farmer/audio/{audio_id}"


def get_audio(audio_id: str) -> bytes | None:
    return _audio.get(audio_id)
