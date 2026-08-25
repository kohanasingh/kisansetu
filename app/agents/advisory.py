"""Agent — Advisory (GPT-4o). The core recommendation engine, covering three
related outputs in one file (shared FPO context, shared reasoning style):

  - storage: nearest / cheapest / least-full warehouse for a crop and
    quantity. A real deterministic lookup over seeded warehouse data — the
    one part of this agent with structured data behind it.
  - crop planning: what to grow next season, reasoned over MSP, a demand
    signal, and weather/soil fit.
  - schemes: which real government schemes fit a farmer or FPO profile.

MSP figures and scheme names are deliberately NOT seeded anywhere in this
repo — they are real public information already in GPT-4o's knowledge, and
fabricating a table would make answers less credible, not more. The prompts
(app/prompts/advisory_crop.md, advisory_schemes.md) instruct the model to
state real figures/names from its own knowledge with an "indicative, may be
outdated" disclaimer. See PROJECT_SPEC.md "Sourcing MSP and schemes".

Drives the live dashboard column on web/demo.html and the advisory panel on
web/fpo.html.
"""
