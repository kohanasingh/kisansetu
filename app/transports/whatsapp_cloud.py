"""Real Meta WhatsApp Cloud API transport — webhook receiver + sender.
Drives the identical orchestrator path (orchestrator/farmer_router.py) as
transports/web_console.py, via transports/base.py's shared interface.

This is a genuine Graph API integration, not a stub — every request shape
below matches Meta's documented webhook payload and Send Message API. It
won't be exercised end-to-end without real Meta credentials
(WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_VERIFY_TOKEN in .env,
currently blank per .env.example — see CLAUDE.md "Tier 2"), but nothing
here is mocked or faked.

OutboundMessage.buttons isn't sent as a WhatsApp interactive message yet —
no agent in this codebase populates .buttons today (see
orchestrator/farmer_router.py), so there is nothing real to wire it to.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.transports.base import InboundMessage, OutboundMessage, Transport

logger = logging.getLogger("kisansetu.whatsapp")

GRAPH_API_VERSION = "v20.0"


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
    if mode == "subscribe" and _verify_token() and token == _verify_token():
        return challenge
    return None


async def _fetch_media(media_id: str) -> tuple[bytes, str] | None:
    """Resolve a Meta media id to raw bytes via two authenticated Graph API
    calls (id -> short-lived URL -> bytes), per Meta's media API."""
    token = _token()
    if not token:
        logger.error("WHATSAPP_TOKEN not configured; cannot fetch media id=%s", media_id)
        return None
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as http:
        meta_resp = await http.get(f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}", headers=headers)
        meta_resp.raise_for_status()
        meta = meta_resp.json()
        bytes_resp = await http.get(meta["url"], headers=headers)
        bytes_resp.raise_for_status()
        return bytes_resp.content, meta.get("mime_type", "audio/ogg")


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
                    media_id = msg.get("audio", {}).get("id")
                    fetched = await _fetch_media(media_id) if media_id else None
                    if fetched:
                        media_bytes, mime = fetched
                        messages.append(InboundMessage(
                            sender=sender, type="audio", media=media_bytes, media_mime=mime,
                            transport="whatsapp_cloud",
                        ))
                    else:
                        logger.warning("could not fetch whatsapp audio media id=%s", media_id)
                elif msg_type == "image":
                    media_id = msg.get("image", {}).get("id")
                    fetched = await _fetch_media(media_id) if media_id else None
                    if fetched:
                        media_bytes, mime = fetched
                        messages.append(InboundMessage(
                            sender=sender, type="image", media=media_bytes, media_mime=mime,
                            text=msg.get("image", {}).get("caption"), transport="whatsapp_cloud",
                        ))
                    else:
                        logger.warning("could not fetch whatsapp image media id=%s", media_id)
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
            resp = await http.post(base_url, headers=headers, json={
                "messaging_product": "whatsapp", "to": message.to,
                "type": "text", "text": {"body": message.text},
            })
            if resp.status_code >= 400:
                logger.error("whatsapp send text failed (%s): %s", resp.status_code, resp.text)

            # WhatsApp has no single message type carrying both text and
            # audio, so a TTS voice note goes out as a second message.
            if message.audio_bytes:
                media_id = await self._upload_media(http, headers, phone_id, message.audio_bytes)
                if media_id:
                    resp = await http.post(base_url, headers=headers, json={
                        "messaging_product": "whatsapp", "to": message.to,
                        "type": "audio", "audio": {"id": media_id},
                    })
                    if resp.status_code >= 400:
                        logger.error("whatsapp send audio failed (%s): %s", resp.status_code, resp.text)

    async def _upload_media(self, http: httpx.AsyncClient, headers: dict, phone_id: str,
                             audio_bytes: bytes) -> str | None:
        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/media"
        resp = await http.post(
            url, headers=headers, data={"messaging_product": "whatsapp"},
            files={"file": ("note.ogg", audio_bytes, "audio/ogg")},
        )
        if resp.status_code >= 400:
            logger.error("whatsapp media upload failed (%s): %s", resp.status_code, resp.text)
            return None
        return resp.json().get("id")
