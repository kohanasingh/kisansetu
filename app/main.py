"""KisanSetu FastAPI app.

Serves three static pages from web/ (no build step):
  GET /                  -> web/landing.html
  GET /demo               -> web/demo.html   (the live demo, its own page)
  GET /fpo                -> web/fpo.html    (FPO dashboard, no login)
  GET /health

APIs (Checkpoint 1 — farmer chat only; FPO/ingestion/climate APIs arrive
with their agents in Tier 2):
  POST /api/farmer/send  -> web-console send (text and/or a voice note)
  GET  /api/farmer/poll  -> web-console poll, matching transports/web_console.py
  GET  /api/farmer/audio/{id} -> serves TTS audio bytes stored in-memory
                                  by transports/web_console.py
  GET  /webhook/whatsapp -> Meta webhook verification handshake
  POST /webhook/whatsapp -> real Meta WhatsApp Cloud API webhook (Tier 2)

send/poll rather than a synchronous reply: the orchestrator call runs as a
background job (app/jobs/queue.py) so the request returns immediately and
the frontend polls for the reply — this is why Cloud Run needs
--no-cpu-throttling (see deploy/cloud_run.md).
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import time

from app.agentlog import clear as clear_agentlog, recent as recent_agentlog
from app.agents import advisory, climate, ingestion
from app.db import store
from app.jobs import scheduler
from app.jobs.queue import enqueue
from app.llm import require_openai_key
from app.orchestrator import dashboard_state, fpo_router, identity
from app.orchestrator.farmer_router import handle_inbound
from app.transports.base import InboundMessage
from app.transports.web_console import WebConsoleTransport, get_audio, poll
from app.transports.web_console import reset as reset_web_console
from app.transports.whatsapp_cloud import WhatsAppCloudTransport, parse_webhook_event, verify_webhook

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kisansetu.main")

WEB_DIR = Path(__file__).parent.parent / "web"

app = FastAPI(title="KisanSetu")
app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")

_web_console = WebConsoleTransport()
_whatsapp = WhatsAppCloudTransport()


@app.on_event("startup")
async def on_startup() -> None:
    require_openai_key()
    scheduler.start()
    logger.info("KisanSetu startup complete.")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/agentlog")
async def agentlog_feed(limit: int = 50) -> JSONResponse:
    """Live agent-activity feed (CLAUDE.md Tier 3 item 15), surfaced on
    web/demo.html — every agent call in this codebase already logs through
    app/agentlog.py; this just exposes that log to the frontend."""
    return JSONResponse(recent_agentlog(limit))


@app.get("/")
async def landing() -> FileResponse:
    return FileResponse(WEB_DIR / "landing.html")


@app.get("/demo")
async def demo() -> FileResponse:
    return FileResponse(WEB_DIR / "demo.html")


@app.get("/fpo")
async def fpo() -> FileResponse:
    return FileResponse(WEB_DIR / "fpo.html")


# --- Farmer chat (web console) -------------------------------------------

@app.post("/api/farmer/send")
async def farmer_send(
    sender: str = Form(..., description="WhatsApp-equivalent phone/identity for this session"),
    text: str | None = Form(None),
    audio: UploadFile | None = File(None),
    image: UploadFile | None = File(None),
) -> JSONResponse:
    if audio is not None:
        media = await audio.read()
        msg = InboundMessage(sender=sender, type="audio", media=media,
                              media_mime=audio.content_type, transport="web_console")
    elif image is not None:
        media = await image.read()
        msg = InboundMessage(sender=sender, type="image", media=media, text=text or None,
                              media_mime=image.content_type, transport="web_console")
    else:
        msg = InboundMessage(sender=sender, type="text", text=text or "", transport="web_console")

    enqueue(handle_inbound(msg, _web_console), name=f"farmer_router:{sender}")
    return JSONResponse({"ok": True})


@app.get("/api/farmer/poll")
async def farmer_poll(sender: str, since: int = 0) -> JSONResponse:
    return JSONResponse(poll(sender, since))


@app.get("/api/farmer/audio/{audio_id}")
async def farmer_audio(audio_id: str) -> Response:
    data = get_audio(audio_id)
    if data is None:
        return Response(status_code=404)
    return Response(content=data, media_type="audio/ogg")


# --- Real WhatsApp (Meta Cloud API) --------------------------------------

@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request) -> Response:
    params = request.query_params
    challenge = verify_webhook(
        params.get("hub.mode"), params.get("hub.verify_token"), params.get("hub.challenge"),
    )
    if challenge is None:
        return Response(status_code=403)
    return Response(content=challenge, media_type="text/plain")


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(payload: dict) -> JSONResponse:
    for msg in await parse_webhook_event(payload):
        enqueue(handle_inbound(msg, _whatsapp), name=f"farmer_router:{msg.sender}")
    return JSONResponse({"ok": True})


@app.get("/api/farmer/dashboard")
async def farmer_dashboard(sender: str) -> JSONResponse:
    return JSONResponse(dashboard_state.get(sender))


@app.post("/demo/reset")
async def demo_reset() -> JSONResponse:
    """Wipe all in-memory session state so a fresh judge can start clean.
    Never touches db/store.py's seeded dataset — only per-session state."""
    reset_web_console()
    dashboard_state.reset()
    identity.reset()
    clear_agentlog()
    return JSONResponse({"ok": True})


# --- Climate Watch (on-demand real check) --------------------------------

@app.post("/api/climate/check")
async def climate_check(fpo_id: str | None = None) -> JSONResponse:
    """Runs the same real Open-Meteo check jobs/scheduler.py does on its
    own timer, right now. Backs the /demo 'Simulate Climate Alert' control
    — an on-demand real check, never a fabricated alert. If conditions are
    calm, this honestly returns no new alerts."""
    if fpo_id:
        fpo = store.get_fpo(fpo_id)
        if fpo is None:
            return JSONResponse({"error": "unknown fpo_id"}, status_code=404)
        alert = await climate.check_fpo(fpo)
        return JSONResponse({"checked": [fpo["name"]], "new_alerts": [alert] if alert else []})

    alerts = await climate.check_all_fpos()
    return JSONResponse({"checked": [f["name"] for f in store.list_fpos()], "new_alerts": alerts})


# --- FPO dashboard (web/fpo.html) ----------------------------------------

@app.get("/api/fpo/list")
async def fpo_list() -> JSONResponse:
    return JSONResponse(store.list_fpos())


@app.get("/api/fpo/overview")
async def fpo_overview(fpo_id: str) -> JSONResponse:
    fpo = store.get_fpo(fpo_id)
    if fpo is None:
        return JSONResponse({"error": "unknown fpo_id"}, status_code=404)

    farmers = store.list_farmers(fpo_id)
    warehouses = store.list_warehouses(fpo_id)
    week_ago = time.time() - 7 * 24 * 3600
    queries_this_week = sum(
        1 for e in recent_agentlog(200)
        if e["agent"] in {"advisory", "farmer_query"}
        and e["ts"] >= week_ago
        and isinstance(e.get("payload"), dict)
        and e["payload"].get("fpo_id") == fpo_id
    )

    return JSONResponse({
        "fpo": fpo,
        "stats": {
            "member_farmers": len(farmers),
            "land_covered_acres": round(sum(f["farm_size_acres"] for f in farmers), 1),
            "storage_available_quintal": sum(w["capacity_quintal"] - w["occupied_quintal"] for w in warehouses),
            "queries_this_week": queries_this_week,
        },
        "alerts": store.recent_alerts(fpo_id, limit=3),
    })


@app.get("/api/fpo/advisory")
async def fpo_advisory(fpo_id: str) -> JSONResponse:
    """FPO-level (not farmer-specific) advisory summary for the dashboard's
    'Advisory for your farmers' panel — same agents/advisory.py functions
    the farmer chat uses, called with no specific farmer."""
    fpo = store.get_fpo(fpo_id)
    if fpo is None:
        return JSONResponse({"error": "unknown fpo_id"}, status_code=404)

    identity_ctx = {
        "fpo": fpo, "farmer": None, "personalized": True,
        "note": "FPO-wide overview, not specific to one farmer.",
    }
    kwargs = dict(language_code="en", language_name="English", identity_ctx=identity_ctx)
    crop_plan, storage, schemes = (
        await advisory.crop_plan("What should farmers in this FPO consider planting this season?", **kwargs),
        await advisory.storage("Which warehouse has the most space available right now?", **kwargs),
        await advisory.schemes("What government schemes are most relevant to farmers here?", **kwargs),
    )
    return JSONResponse({"crop_plan": crop_plan, "storage": storage, "schemes": schemes})


@app.post("/api/fpo/chat")
async def fpo_chat(fpo_id: str = Form(...), text: str = Form(...)) -> JSONResponse:
    """FPO staff chatbot ('Ask KisanSetu' on web/fpo.html) — orchestrator/fpo_router.py."""
    reply = await fpo_router.answer(fpo_id, text)
    return JSONResponse({"reply": reply})


# --- Ingestion (web/fpo.html "Recent uploads") ---------------------------

@app.post("/api/fpo/upload")
async def fpo_upload(fpo_id: str = Form(...), file: UploadFile = File(...)) -> JSONResponse:
    if store.get_fpo(fpo_id) is None:
        return JSONResponse({"error": "unknown fpo_id"}, status_code=404)

    data = await file.read()
    filename = file.filename or "upload"
    if filename.lower().endswith(_IMAGE_EXTENSIONS) or (file.content_type or "").startswith("image/"):
        rows = await ingestion.parse_scan(data, mime=file.content_type or "image/jpeg")
    else:
        try:
            rows = ingestion.parse_excel(data, filename)
        except Exception as e:  # noqa: BLE001 — surface a clean error, not a 500
            return JSONResponse({"error": f"could not parse file: {e}"}, status_code=400)

    batch = ingestion.stage(fpo_id, filename, rows)
    return JSONResponse(batch)


@app.get("/api/fpo/uploads")
async def fpo_uploads(fpo_id: str) -> JSONResponse:
    return JSONResponse(ingestion.list_batches(fpo_id))


@app.post("/api/fpo/upload-sample")
async def fpo_upload_sample(fpo_id: str) -> JSONResponse:
    """Backs the /demo 'Simulate FPO Batch Upload' control — runs the real
    ingestion parse (pandas/openpyxl) against a bundled sample register, so
    a judge can see staged-for-review rows without needing a file of their
    own on hand. Same staging/approve/discard path as a real upload."""
    if store.get_fpo(fpo_id) is None:
        return JSONResponse({"error": "unknown fpo_id"}, status_code=404)
    sample_path = Path(__file__).parent / "fixtures" / "sample_register.xlsx"
    rows = ingestion.parse_excel(sample_path.read_bytes(), sample_path.name)
    batch = ingestion.stage(fpo_id, "sample_register.xlsx (simulated FPO upload)", rows)
    return JSONResponse(batch)


@app.post("/api/fpo/uploads/{batch_id}/approve")
async def fpo_upload_approve(batch_id: str) -> JSONResponse:
    batch = ingestion.approve(batch_id)
    if batch is None:
        return JSONResponse({"error": "batch not found or not pending"}, status_code=404)
    return JSONResponse(batch)


@app.post("/api/fpo/uploads/{batch_id}/discard")
async def fpo_upload_discard(batch_id: str) -> JSONResponse:
    batch = ingestion.discard(batch_id)
    if batch is None:
        return JSONResponse({"error": "batch not found or not pending"}, status_code=404)
    return JSONResponse(batch)
