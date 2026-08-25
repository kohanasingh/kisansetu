<!-- Versioned prompt: farmer_general_answer. Loaded via
llm.load_prompt("farmer_general_answer").

Powers agents/farmer_query.py. Must instruct the model to answer ONLY from
the facts dict supplied by the caller (farmer's record + FPO context +
recent alerts), to say plainly that it doesn't know when a fact is absent
rather than guessing, and to reply in the farmer's own language — not
defaulting to Hindi or English. -->
