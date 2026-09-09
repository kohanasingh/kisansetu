# KisanSetu — Project Spec

Single source of truth for what to build. Companion docs:
`CLAUDE.md` (constraints + build order — read first), `ARCHITECTURE.md`
(folder structure + data flow), `DESIGN.md` (the approved UI).

## The problem (use this framing in the landing page copy)

India's agricultural value chain is broken at the information layer:

- FPOs already hold years of records — yields, land sizes, crops,
  farmer phone numbers — sitting in files nobody opens. That data could
  benefit every member farmer and never does.
- Farmers don't know what to grow, where to sell, what suits their soil,
  what MSP they could get at a local mandi, which fertilizer to use, or
  which government schemes they qualify for.
- Government schemes and benefits go unclaimed and fail to reach the
  regions they were designed for.

KisanSetu takes the unorganized, underutilized data FPOs keep, combines
it with market demand and MSP context, and turns it into advice a
farmer can act on — to raise income and cut post-harvest losses.

(This corresponds to a Smart India Hackathon 2025 problem statement in
the smart-crop-advisory space; the framing above is the authoritative
version for this project.)

## Two actors

- **FPO staff** — open the dashboard (`/fpo`), upload farmer/crop/yield
  records as Excel or scanned paper documents, see AI-generated
  advisory (storage, crop planning, schemes), and can ask a chatbot
  questions about their own data.
- **Farmers** — talk to a voice-enabled assistant on their own real
  WhatsApp, in their own language, and get answers personalized to
  their record and their FPO's data — or, failing that, the nearest
  FPO's, or general knowledge as a last resort. The website's `/demo`
  page mirrors this exact conversation so it can be tried without a
  live Meta phone number.

## Why no RAG in this prototype

No FPO has onboarded yet — there is no real farmer data. Building a
vector DB against data that doesn't exist is wasted work. Instead, all
personalization comes from plain function calls (`db/store.py`) that
fetch structured rows and inject them into the prompt as JSON — the
same pattern the reference project used for its own database-state
injection. This is the documented seam to replace with real ingestion +
a vector DB once actual FPO data exists.

## Data model (`db/dummy_data.py`)

**Only fabricate what has no real-world source.** MSP prices and
government scheme details are real, public, and already in GPT-4o's
knowledge — do NOT build tables for them (see "Sourcing MSP and
schemes"). Seed only the FPO-private facts:

Seed 2-3 FPOs, ~10-15 farmers, 4-6 warehouses:

```
fpo:         id, name, region_name, lat, lon, contact_phone
farmer:      id, name, phone, fpo_id, village, farm_size_acres,
             crops: [str], lat, lon
crop_record: farmer_id, crop, season, year, yield_quintal
warehouse:   id, name, lat/lon, capacity_quintal, occupied_quintal,
             cost_per_quintal
alert:       id, fpo_id, kind (drought|storm|heavy_rain), severity,
             message, created_at
```

All read ONLY through `db/store.py` — no other module imports
`dummy_data.py` directly.

## Agents

### 1. Ingestion (`agents/ingestion.py`)
- Excel/CSV -> parsed with pandas/openpyxl, validated, staged.
- Scanned documents (photos/PDFs of paper registers) -> read via
  **GPT-4o Vision directly**, no separate OCR engine. Returns
  structured JSON matching the schema above. This is the answer to
  "how do we make scanned documents machine-readable."
- **Nothing auto-merges.** Output is staged for FPO review on `/fpo`
  before it reaches `db/store.py`.

### 2. Advisory (`agents/advisory.py`)
One file, three related outputs:
- **Storage**: nearest / cheapest / least-full warehouse for a crop and
  quantity. This is a real code lookup over seeded warehouse data.
- **Crop planning**: what to grow next season, reasoned over MSP, a
  demand signal, and weather/soil fit.
- **Schemes**: which real government schemes fit a farmer/FPO profile.

**Provider: Gemini (`gemini-flash-lite-latest`), not GPT-4o.** This is
the one agent in the codebase that moves off OpenAI, to cut cost —
everything else (intent classification, farmer_query, Whisper, TTS,
Vision) stays on GPT-4o exactly as originally specified. Every call goes
through `llm.chat_json_gemini()` / `llm.chat_text_gemini()` (same
signature shape as their GPT-4o counterparts, so this file has no
provider-specific branching). Resilience: retry with backoff first (same
pattern as every other `app/llm.py` call); on continued Gemini failure,
fall back to GPT-4o for that call rather than surfacing an error to the
FPO, and log the fallback through `app/agentlog.py` so it's visible on
the demo's agent-activity feed rather than silent.

#### Sourcing MSP and schemes
No `msp_price` or `scheme` table exists anywhere in this repo, by
design. The prompts instruct the model to state real MSP figures and
real scheme names (PM-KISAN, PMFBY, KCC, Soil Health Card, e-NAM, etc.)
from its own knowledge, and to append a plain disclaimer that figures
are indicative and may be out of date. Fabricating a fake table would
make answers *less* credible. The training-cutoff staleness is a
disclosed limitation, documented in the README next to the RAG note; a
production version would ground these in a live data source.

### 3. Climate watch (`agents/climate.py` + `jobs/scheduler.py`)
Polls Open-Meteo per FPO region on a periodic in-process tick,
evaluates thresholds (heavy rain, drought risk, storm), writes
qualifying alerts to `db/store.py`. Surfaced on `/fpo` and as a `/demo`
trigger. On real WhatsApp these become outbound advisory messages.

### 4. Farmer Q&A (`agents/farmer_query.py`)
Assembles a facts dict — the farmer's record + their FPO's advisory
context + recent alerts — and answers in the farmer's language,
grounded only in that dict. Also handles questions accompanied by a
crop photo or soil-report scan via GPT-4o Vision (read-only; a farmer's
question never writes data).

## Orchestrator

### Identity resolution (`orchestrator/identity.py`)
Runs first on every farmer message. Four paths:
1. Registered phone recognized -> phone->FPO lookup -> full context.
2. Not registered, names their FPO -> fuzzy match -> same context.
3. Not registered, gives a village/location -> nearest FPO by haversine
   -> borrow that FPO's context.
4. No FPO within a reasonable radius -> general knowledge only, and the
   assistant says so plainly rather than pretending to have local data.

### Routers
`farmer_router.py`: identity -> GPT-4o JSON-mode intent classification
(advisory / storage / scheme / alert / general) -> dispatch. Intent
classification stays on GPT-4o (fires on every message; must not be
flaky) even though the `advisory` intent it may dispatch to is served by
`agents/advisory.py` running on Gemini.
`fpo_router.py`: no identity step needed; classify + dispatch for staff.
Same rule — intent classification here stays GPT-4o too.

## Voice and language

Multilingual voice is **Tier 1**, not a stretch goal — farmers using
their own language is the point of the product.

- Whisper transcribes inbound audio; it handles major Indian languages
  natively. Language-hint where supported, auto-detect fallback
  otherwise (Whisper rejects hints for some languages and must not
  crash intake).
- `gpt-4o-mini-tts` speaks replies back.
- `services/translate.py` (Gemini flash-lite, via `llm.chat_text_gemini()`)
  covers languages where GPT-4o's native output is weak — fail-open, so
  any error returns the original text rather than breaking the reply.
  This and `agents/advisory.py` are the only two Gemini callers in the
  codebase; everything else stays on GPT-4o (see CLAUDE.md hard
  constraints).
- A judge speaking Punjabi, Bengali, Tamil, or Marathi must get a
  coherent spoken reply in that language. Don't hardcode the reply path
  to Hindi/English.
- The FPO chatbot can be text-first with optional voice — it's an
  internal staff tool.

## The demo (`/demo`) — live, not scripted

The chat column is a **real agent**. A judge can type or speak and get a
genuine answer grounded in the seeded data; all four identity paths
actually work if tried. The control buttons exist only to fire
*external* events a conversation can't produce on its own — a climate
alert, an FPO batch upload, an agent-activity view. Never present the
chat as a replay.

On first message the assistant asks — exactly as it would over real
WhatsApp — for a registered number, an FPO name, or a village. The page
lists 2-3 sample inputs so all four identity paths can be exercised
without real data.

## Explicitly out of scope (document, don't build)

- A real vector DB / RAG pipeline (documented upgrade path only).
- Login/auth of any kind; `/fpo` is directly reachable.
- A real demand-forecasting model — the crop-planning demand signal is
  LLM-reasoned, clearly labeled as an approximation in UI and README.
- Real farmer/FPO registration, or payments.
- Live testing of the WhatsApp transport against a real Meta number —
  implement it genuinely, but verification needs credentials this
  prototype won't have during initial development.
