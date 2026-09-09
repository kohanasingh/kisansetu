"""Transport adapter interface, implemented by both real transports —
whatsapp_cloud.py and web_console.py. The orchestrator only ever talks to
this interface, never to a transport directly, so the same conversation
logic serves a farmer on real WhatsApp and a judge on web/demo.html.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Button:
    id: str
    label: str


@dataclass
class InboundMessage:
    sender: str
    type: str  # "text" | "audio" | "image" | "button"
    text: str | None = None
    media: bytes | None = None
    media_mime: str | None = None
    transport: str = "unknown"


@dataclass
class OutboundMessage:
    to: str
    text: str
    audio_bytes: bytes | None = None  # raw TTS output; each transport decides how
                                       # to deliver it (in-memory URL for the web
                                       # console, a Meta media upload for WhatsApp)
    image_url: str | None = None
    buttons: list[Button] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


class Transport(ABC):
    """One instance per transport; registered with the router."""

    name: str = "base"

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None: ...

    def supports_buttons(self) -> bool:
        return True
