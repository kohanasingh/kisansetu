"""Inbound voice: Whisper transcription. Whisper handles major Indian
languages natively; use a language hint where supported and fall back to
auto-detect otherwise — Whisper rejects hints for some languages and
must not crash intake when it does.
"""
