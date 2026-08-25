"""Agent — Farmer Q&A. The grounded free-form answer path behind the farmer
chat, on both transports.

Assembles a facts dict (the farmer's own record + their resolved FPO's
advisory context + recent regional alerts) and lets GPT-4o answer in the
farmer's own language, grounded ONLY in what that dict contains. If a fact
isn't in the dict, the model says it doesn't know rather than guessing —
this anti-hallucination discipline is a hard constraint (CLAUDE.md).

Multilingual is Tier 1: the reply path must not be hardcoded to
Hindi/English. Also handles questions accompanied by a crop photo or soil
report scan via GPT-4o Vision — read-only, since a farmer's question never
writes data.
"""
