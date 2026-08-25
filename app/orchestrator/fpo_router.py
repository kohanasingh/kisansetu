"""Orchestrator entry point for the FPO staff chatbot on web/fpo.html.

Simpler than farmer_router.py — no identity resolution step, since the
dashboard is scoped to a single FPO (there is no login in this prototype;
see CLAUDE.md "What NOT to build"). Classifies intent via GPT-4o JSON-mode
and dispatches to agents/advisory.py, agents/climate.py, or ingestion
status queries.
"""
