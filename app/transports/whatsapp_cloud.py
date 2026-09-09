"""Real Meta WhatsApp Cloud API transport — webhook receiver + sender.
Drives the identical orchestrator path (orchestrator/farmer_router.py) as
transports/web_console.py, via transports/base.py's shared interface.

This is a genuine Graph API integration, not a stub — every request shape
below matches Meta's documented webhook payload and Send Message API. It
won't be exercised end-to-end without real Meta credentials
(WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN in .env,
currently blank per .env.example — see CLAUDE.md "Tier 2"), but nothing
here is mocked or faked.

Every Graph API call goes through _get_with_retry/_post_with_retry, which
share the same retry/backoff pattern as every LLM call in app/llm.py (via
app/retry.py) — a transient network blip talking to Meta no longer drops
a message or reply silently.

OutboundMessage.buttons isn't sent as a WhatsApp interactive message yet —
no agent in this codebase populates .buttons today (see
orchestrator/farmer_router.py), so there is nothing real to wire it to.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.retry import with_retry
from app.transports.base import InboundMessage, OutboundMessage, Transport

logger = logging.getLogger("kisansetu.whatsapp")

GRAPH_API_VERSION = "v20.0"


class WhatsAppError(Exception):
    """Raised after retries are exhausted talking to Meta's Graph API."""


def _token() -> str:
    return os.environ.get("WHATSAPP_TOKEN", "")


def _phone_number_id() -> str:
    return os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")


def _verify_token() -> str:
    return os.environ.get("WHATSAPP_VERIFY_TOKEN", "")


def verify_webhook(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Meta's GET handshake when the webhook URL is registered: echo
    `challenge` back only if mode is 'subscribe' and `token` matches our
    configured verify token. Returns None (caller should 403) otherwise."""
    expected = _verify_token()
    if mode == "subscribe" and expected and token == expected:
        return challenge
    return None


async def _get_with_retry(http: httpx.AsyncClient, url: str, *, what: str, **kwargs) -> httpx.Response:
    async def call():
        resp = await http.get(url, **kwargs)
        resp.raise_for_status()
        return resp
    return await with_retry(call, what=what, exceptions=(httpx.HTTPError,), error_cls=WhatsAppError)


async def _post_with_retry(http: httpx.AsyncClient, url: str, *, what: str, **kwargs) -> httpx.Response:
    async def call():
        resp = await http.post(url, **kwargs)
        resp.raise_for_status()
        return resp
    return await with_retry(call, what=what, exceptions=(httpx.HTTPError,), error_cls=WhatsAppError)


async def _fetch_media(media_id: str) -> tuple[bytes, str] | None:
    """Resolve a Meta media id to raw bytes via two authenticated Graph API
    calls (id -> short-lived URL -> bytes), per Meta's media API. Returns
    None if either call fails even after retries."""
    token = _token()
    if not token:
        logger.error("WHATSAPP_TOKEN not configured; cannot fetch media id=%s", media_id)
        return None
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=20) as http:
            meta_resp = await _get_with_retry(
                http, f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}",
                what=f"whatsapp.fetch_media_meta[{media_id}]", headers=headers,
            )
            meta = meta_resp.json()
            bytes_resp = await _get_with_retry(
                http, meta["url"], what=f"whatsapp.fetch_media_bytes[{media_id}]", headers=headers,
            )
            return bytes_resp.content, meta.get("mime_type", "audio/ogg")
    except WhatsAppError:
        logger.exception("failed to fetch whatsapp media id=%s after retries", media_id)
        return None


async def _media_inbound_message(msg: dict, media_field: str, msg_type: str, sender: str,
                                  *, caption_field: str | None = None) -> InboundMessage | None:
    """Shared by the 'audio' and 'image' webhook branches — both fetch a
    media id and build an InboundMessage the same way, differing only in
    the message type and whether a caption is attached."""
    media_id = msg.get(media_field, {}).get("id")
    if not media_id:
        return None
    fetched = await _fetch_media(media_id)
    if fetched is None:
        logger.warning("could not fetch whatsapp %s media id=%s", media_field, media_id)
        return None
    media_bytes, mime = fetched
    caption = msg.get(media_field, {}).get(caption_field) if caption_field else None
    return InboundMessage(
        sender=sender, type=msg_type, media=media_bytes, media_mime=mime,
        text=caption, transport="whatsapp_cloud",
    )


async def parse_webhook_event(payload: dict) -> list[InboundMessage]:
    """Meta sends a batch payload; pull every inbound message out of it.
    Shape matches entry[].changes[].value.messages[] per Meta's docs.
    Delivery-receipt-only payloads (statuses, no messages) yield []."""
    messages: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                sender = msg.get("from", "")
                msg_type = msg.get("type")

                if msg_type == "text":
                    messages.append(InboundMessage(
                        sender=sender, type="text", text=msg.get("text", {}).get("body", ""),
                        transport="whatsapp_cloud",
                    ))
                elif msg_type == "audio":
                    inbound = await _media_inbound_message(msg, "audio", "audio", sender)
                    if inbound:
                        messages.append(inbound)
                elif msg_type == "image":
                    inbound = await _media_inbound_message(
                        msg, "image", "image", sender, caption_field="caption",
                    )
                    if inbound:
                        messages.append(inbound)
                elif msg_type == "interactive":
                    reply = (msg.get("interactive", {}).get("button_reply")
                             or msg.get("interactive", {}).get("list_reply"))
                    if reply:
                        messages.append(InboundMessage(
                            sender=sender, type="button", text=reply.get("title"),
                            transport="whatsapp_cloud",
                        ))
                else:
                    logger.info("ignoring unsupported whatsapp message type: %s", msg_type)
    return messages


class WhatsAppCloudTransport(Transport):
    name = "whatsapp_cloud"

    async def send(self, message: OutboundMessage) -> None:
        token, phone_id = _token(), _phone_number_id()
        if not token or not phone_id:
            logger.error("WHATSAPP_TOKEN/WHATSAPP_PHONE_NUMBER_ID not configured; cannot send to %s",
                         message.to)
            return

        base_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages"
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=20) as http:
            try:
                await _post_with_retry(http, base_url, what="whatsapp.send_text", headers=headers, json={
                    "messaging_product": "whatsapp", "to": message.to,
                    "type": "text", "text": {"body": message.text},
                })
            except WhatsAppError:
                logger.exception("whatsapp send text failed after retries (to=%s)", message.to)

            # WhatsApp has no single message type carrying both text and
            # audio, so a TTS voice note goes out as a second message.
            if message.audio_bytes:
                media_id = await self._upload_media(http, headers, phone_id, message.audio_bytes)
                if media_id:
                    try:
                        await _post_with_retry(http, base_url, what="whatsapp.send_audio", headers=headers, json={
                            "messaging_product": "whatsapp", "to": message.to,
                            "type": "audio", "audio": {"id": media_id},
                        })
                    except WhatsAppError:
                        logger.exception("whatsapp send audio failed after retries (to=%s)", message.to)

    async def _upload_media(self, http: httpx.AsyncClient, headers: dict, phone_id: str,
                             audio_bytes: bytes) -> str | None:
        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/media"
        try:
            resp = await _post_with_retry(
                http, url, what="whatsapp.upload_media", headers=headers,
                data={"messaging_product": "whatsapp"},
                files={"file": ("note.ogg", audio_bytes, "audio/ogg")},
            )
            return resp.json().get("id")
        except WhatsAppError:
            logger.exception("whatsapp media upload failed after retries")
            return None
