"""Transport adapter interface, implemented by both real transports —
whatsapp_cloud.py and web_console.py. The orchestrator only ever talks to
this interface, never to a transport directly, so the same conversation
logic serves a farmer on real WhatsApp and a judge on web/demo.html.

Defines InboundMessage, OutboundMessage, Button, and Transport.send().
"""
