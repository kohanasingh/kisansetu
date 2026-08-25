"""WhatsApp-styled demo console transport — a real client (in-memory
per-session outbox, polled by the frontend), driving the identical
orchestrator path as transports/whatsapp_cloud.py.

Its job is to let a tester use exactly what a farmer would see on their own
WhatsApp, without a live Meta phone number. This is a REAL live agent path,
not a scripted playback — a judge can type or speak and get a genuine
grounded answer, and all four identity-resolution paths work if tried.
(The demo control buttons on web/demo.html are separate: they only fire
external events like a climate alert or an FPO batch upload.)

Also used, more simply, for the FPO staff chatbot on web/fpo.html.
"""
