"""Gemini (gemini-flash-lite-latest) translation, covering Indian
languages where GPT-4o's native output is weak.

MUST be fail-open: any error, missing API key, or already-native-language
input returns the original text untouched. A translation failure can
never break a reply.
"""
