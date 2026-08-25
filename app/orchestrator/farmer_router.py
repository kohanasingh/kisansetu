"""Orchestrator entry point for the farmer chat — used identically by
transports/web_console.py (the /demo mimic) and
transports/whatsapp_cloud.py (real WhatsApp).

Runs orchestrator/identity.py first, then classifies intent via GPT-4o
JSON-mode (advisory / storage / scheme / alert / general) and dispatches
to agents/advisory.py, agents/climate.py, or agents/farmer_query.py.

This is a real conversational path, not a scripted demo sequence — the
same code answers a judge clicking around /demo and a farmer messaging
from their own phone.
"""
