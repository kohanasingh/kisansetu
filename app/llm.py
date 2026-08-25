"""Shared OpenAI client — the single place every GPT-4o call goes through.

Provides chat_json() for structured JSON-mode output, chat_text() for
free-form replies, image_content() for Vision calls, load_prompt() to load
versioned prompt files from app/prompts/ (never inline prompt strings in
agent code), and a shared retry/backoff wrapper so every agent inherits the
same resilience.

Hard constraint: agents never instantiate or call the OpenAI client
directly — always through here. See CLAUDE.md.
"""
