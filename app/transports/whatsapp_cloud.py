"""Real Meta WhatsApp Cloud API transport — farmers are meant to actually be
reached here; this is the product, not a stand-in.

Webhook receiver (verifies WHATSAPP_VERIFY_TOKEN, parses inbound text /
audio / image messages into InboundMessage) plus outbound sender (text and
voice-note audio via WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID).

Drives the exact same orchestrator/farmer_router.py path as
web_console.py — web_console is the demo mimic of THIS, not the other way
around. Implement it for real; it simply won't be live-verified during
initial development without Meta credentials (see PROJECT_SPEC.md
"Explicitly out of scope").
"""
