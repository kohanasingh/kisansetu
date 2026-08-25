"""Agent — Ingestion. Turns whatever an FPO uploads into structured data:

  - Excel/CSV: parsed directly (pandas/openpyxl), row-validated.
  - Scanned documents (photos or PDFs of paper registers): read via GPT-4o
    Vision directly — no separate OCR engine. The model returns structured
    JSON matching the db schema. This is the answer to "how do we make
    scanned paper records machine-readable."

Hard constraint: nothing auto-merges. Parsed output is STAGED and shown to
FPO staff for review/accept on web/fpo.html before it reaches db/store.py.
The dashboard UI must make this gate visible (see DESIGN.md, fpo.html
"Recent uploads" panel).
"""
