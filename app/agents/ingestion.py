"""Agent — Ingestion. Turns FPO paperwork into staged farmer records: Excel/
CSV parsed with pandas/openpyxl, scanned paper registers read directly by
GPT-4o Vision (no separate OCR engine). Nothing here ever reaches
db/store.py's farmer roster automatically — every batch is staged in
memory and only merged in when FPO staff approve it via web/fpo.html
("Recent uploads"). See CLAUDE.md's "Ingestion never auto-merges".
"""

from __future__ import annotations

import io
import time
import uuid

import pandas as pd

from app.db import store
from app.llm import chat_json, image_content, load_prompt

# Recognized column names -> our schema field, case-insensitive, tried in order.
_COLUMN_ALIASES = {
    "name": ["name", "farmer name", "farmer_name"],
    "phone": ["phone", "mobile", "phone number", "contact", "mobile number"],
    "village": ["village", "village name"],
    "farm_size_acres": ["farm_size_acres", "land size", "land (acres)", "acres", "farm size"],
    "crops": ["crops", "crop", "crops grown"],
}

_batches: dict[str, dict] = {}


def _match_column(columns: list[str], aliases: list[str]) -> str | None:
    lower = {c.lower().strip(): c for c in columns}
    for alias in aliases:
        if alias in lower:
            return lower[alias]
    return None


def parse_excel(file_bytes: bytes, filename: str) -> list[dict]:
    """Real pandas/openpyxl parse — no invented rows. Unrecognized columns
    are ignored; missing recognized ones come through as null/empty."""
    buf = io.BytesIO(file_bytes)
    if filename.lower().endswith(".csv"):
        df = pd.read_csv(buf)
    else:
        df = pd.read_excel(buf, engine="openpyxl")

    columns = list(df.columns)
    field_cols = {field: _match_column(columns, aliases) for field, aliases in _COLUMN_ALIASES.items()}

    rows = []
    for _, record in df.iterrows():
        def get(field):
            col = field_cols[field]
            if col is None:
                return None
            val = record[col]
            return None if pd.isna(val) else val

        crops_raw = get("crops")
        crops = [c.strip() for c in str(crops_raw).split(",") if c.strip()] if crops_raw else []
        farm_size = get("farm_size_acres")
        rows.append({
            "name": str(get("name")) if get("name") is not None else None,
            "phone": str(get("phone")) if get("phone") is not None else None,
            "village": str(get("village")) if get("village") is not None else None,
            "farm_size_acres": float(farm_size) if farm_size is not None else None,
            "crops": crops,
            "confidence": "high",
            "flags": [] if field_cols["name"] and field_cols["village"] else ["some expected columns not found in file"],
        })
    return rows


async def parse_scan(image_bytes: bytes, mime: str = "image/jpeg") -> list[dict]:
    """GPT-4o Vision reads a photographed/scanned paper register directly —
    no separate OCR engine. Flags uncertain fields rather than guessing."""
    system_prompt = load_prompt("ingestion_scan_ocr")
    user_content = [
        {"type": "text", "text": "Read this farmer register and extract every row you can."},
        image_content(image_bytes, mime=mime),
    ]
    result = await chat_json(system_prompt, user_content, what="ingestion.parse_scan")
    return result.get("rows") or []


def stage(fpo_id: str, source_label: str, rows: list[dict]) -> dict:
    batch_id = uuid.uuid4().hex
    batch = {
        "id": batch_id, "fpo_id": fpo_id, "source": source_label, "rows": rows,
        "row_count": len(rows), "status": "pending", "created_at": time.time(),
    }
    _batches[batch_id] = batch
    return batch


def list_batches(fpo_id: str) -> list[dict]:
    return sorted(
        (b for b in _batches.values() if b["fpo_id"] == fpo_id),
        key=lambda b: b["created_at"], reverse=True,
    )


def get_batch(batch_id: str) -> dict | None:
    return _batches.get(batch_id)


def approve(batch_id: str) -> dict | None:
    batch = _batches.get(batch_id)
    if not batch or batch["status"] != "pending":
        return None
    store.add_farmers(batch["fpo_id"], batch["rows"])
    batch["status"] = "approved"
    return batch


def discard(batch_id: str) -> dict | None:
    batch = _batches.get(batch_id)
    if not batch or batch["status"] != "pending":
        return None
    batch["status"] = "discarded"
    return batch
