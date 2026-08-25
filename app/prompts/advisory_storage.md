<!-- Versioned prompt: advisory_storage. Loaded via
llm.load_prompt("advisory_storage").

Powers the storage branch of agents/advisory.py. Unlike the crop and scheme
prompts, this one reasons over REAL structured data — the seeded warehouse
table (capacity, occupancy, cost per quintal, distance). Instruct the model
to recommend from the supplied candidates only, and to state the tradeoff
(nearest vs cheapest vs most available) rather than silently picking one. -->
