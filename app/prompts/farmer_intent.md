<!-- Versioned prompt: farmer_intent. Loaded via llm.load_prompt("farmer_intent").

Classifies an inbound farmer message into one intent (advisory / storage /
scheme / alert / general) using GPT-4o JSON-mode, so
orchestrator/farmer_router.py can dispatch. Written when that router is
implemented. Prompts live in files, never inline in agent code. -->
