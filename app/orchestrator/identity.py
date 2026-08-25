"""Farmer identity resolution — runs before intent classification on every
inbound farmer message. Four paths, in order:

  1. Registered phone recognized -> phone->FPO lookup -> full personalized
     context.
  2. Not registered, farmer names their FPO -> fuzzy/substring match against
     the FPO table -> same personalized context.
  3. Not registered, no FPO named, farmer gives a village or location ->
     nearest FPO via services/geo.py haversine distance -> borrow that
     FPO's context.
  4. No FPO within a reasonable radius -> no personalization, general
     knowledge only, and the assistant says so plainly rather than
     pretending to have local data.

Returns a context dict that farmer_query.py and advisory.py inject into
the prompt. That dict IS the RAG substitute for this prototype — see
PROJECT_SPEC.md "Why no RAG in this prototype".
"""
