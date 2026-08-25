"""Data access layer — every query goes through here, never through
dummy_data.py directly. Backed by the in-memory seeded dataset for the
prototype, with signatures written as if a real DB were behind them
(get_fpo, get_farmer_by_phone, find_fpo_by_name, nearest_fpo_to,
list_warehouses, save_alert, recent_alerts, stage_ingested_batch,
approve_staged_batch, discard_staged_batch) so swapping in Supabase +
a RAG retrieval step later is a same-signature change, not a rewrite of
calling code.

Note there is deliberately NO msp_for_crop() or schemes_for_profile() —
those facts are not seeded anywhere; the advisory agent draws them from
GPT-4o's own knowledge. See PROJECT_SPEC.md "Sourcing MSP and schemes".

Includes an asyncio.Lock to serialize concurrent writes, matching the
reference project's pattern.
"""
